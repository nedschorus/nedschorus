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
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
import types
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
ADMISSION_WAIT_CEILING_SECONDS = load_test_suite_runner().TEST_SUITE_ADMISSION_WAIT_CEILING_SECONDS


def cosmic_ray_timeout_line_and_test_command_words_for_limit(limit):
    """The config's timeout line and the test command's first words, for this limit: cosmic-ray
    waits for the admission ceiling and the limit, then for the test command's backstop to stop
    the runner."""
    return (f"timeout = {float(limit + ADMISSION_WAIT_CEILING_SECONDS + 2 * EXTRA_SECONDS)!r}\n",
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
if tool == "python":
    worktrees = arguments[6:]
    if plan.get("init_sessions"):
        # As the parallel workers do: a result for each mutant asked for. A mutant that has a
        # result already cannot be given a second, so running one twice fails this tool.
        import sqlite3
        connection = sqlite3.connect(arguments[3])
        asked_for = ([row[0] for row in connection.execute(
            "SELECT job_id FROM work_items WHERE job_id NOT IN (SELECT job_id FROM work_results)")]
            if arguments[4] == "all" else arguments[4].split(","))
        for job_id in asked_for:
            connection.execute("INSERT INTO work_results (job_id, worker_outcome, output, "
                               "test_outcome, diff) VALUES (?, 'NORMAL', ?, 'KILLED', NULL)",
                               (job_id, plan["killed_output"]))
        connection.commit()
        connection.close()
    (control / "parallel-workers.json").write_text(json.dumps([
        [worktree, subprocess.run(["git", "-C", worktree, "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()]
        for worktree in worktrees]))
    print("a parallel worker failed", file=sys.stderr)
    sys.exit(plan.get("parallel_exit", 0))
if tool == "cr-filter-git":
    sys.exit(plan.get("filter_exit", 0))
if tool in ("cr-filter-pragma", "cr-filter-lines"):
    sys.exit(plan.get(tool + "_exit", 0))
command = arguments[0]
if command == "baseline" and plan.get("baseline_cannot_import_cosmic_ray"):
    # As a venv whose attrs sources /tmp's cleaner deleted: cosmic-ray dies on import.
    print("ImportError: cannot import name 'asdict' from 'attrs' (unknown location)",
          file=sys.stderr)
    sys.exit(1)
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
if command == "init" and plan.get("init_sessions"):
    # A session as cosmic-ray 8.7.0 makes it: a random job_id for each mutant at every init,
    # and a SKIPPED result for a mutant a filter skipped.
    import sqlite3, uuid
    config_text = pathlib.Path(arguments[1]).read_text()
    module_path = json.loads(re.search(r"^module-path = (.*)$", config_text,
                                       re.MULTILINE).group(1))
    connection = sqlite3.connect(arguments[2])
    connection.executescript(
        "CREATE TABLE work_items (job_id TEXT PRIMARY KEY);"
        "CREATE TABLE mutation_specs (module_path, operator_name, operator_args, occurrence, "
        "start_pos_row, start_pos_col, end_pos_row, end_pos_col, definition_name, "
        "job_id TEXT PRIMARY KEY);"
        "CREATE TABLE work_results (job_id TEXT PRIMARY KEY, worker_outcome, output, "
        "test_outcome, diff);")
    for operator, line, skipped_by_a_filter in plan["init_sessions"][module_path]:
        job_id = uuid.uuid4().hex
        connection.execute("INSERT INTO work_items VALUES (?)", (job_id,))
        connection.execute("INSERT INTO mutation_specs VALUES (?, ?, '{{}}', 0, ?, 4, ?, 9, NULL, ?)",
                           (module_path, operator, line, line, job_id))
        if skipped_by_a_filter:
            connection.execute("INSERT INTO work_results (job_id, worker_outcome) "
                               "VALUES (?, 'SKIPPED')", (job_id,))
    connection.commit()
    connection.close()
    sys.exit(0)
if command == "init":
    pathlib.Path(arguments[2]).write_text("session")
    if plan.get("init_makes_kept_session_a_directory"):
        kept = pathlib.Path(arguments[2][:-len(".partial")])
        (kept / "in-the-way").mkdir(parents=True)
    sys.exit(0)
if command == "exec":
    import time
    time.sleep(plan.get("exec_sleep_seconds", 0))
    sys.exit(plan.get("exec_exit", 0))
if command == "dump":
    if pathlib.Path(arguments[1]).read_bytes() == b"baseline":
        if plan.get("baseline_dump_exit"):
            print("Traceback (most recent call last): the session cannot be read")
            sys.exit(plan["baseline_dump_exit"])
        lines = plan.get("baseline_dump", [[{{"job_id": "baseline", "mutations": []}},
                                             {{"worker_outcome": "normal", "output": "",
                                              "test_outcome": "survived", "diff": None}}]])
    elif plan.get("init_sessions"):
        import sqlite3
        connection = sqlite3.connect(arguments[1])
        lines = []
        for job_id, module_path, operator, line in connection.execute(
                "SELECT job_id, module_path, operator_name, start_pos_row FROM mutation_specs"):
            row = connection.execute("SELECT worker_outcome, output, test_outcome, diff FROM "
                                     "work_results WHERE job_id = ?", (job_id,)).fetchone()
            lines.append([
                {{"job_id": job_id, "mutations": [{{
                    "module_path": module_path, "operator_name": operator, "occurrence": 0,
                    "start_pos": [line, 4], "end_pos": [line, 9], "operator_args": {{}}}}]}},
                None if row is None else {{
                    "worker_outcome": row[0].lower(), "output": row[1],
                    "test_outcome": row[2].lower() if row[2] else None, "diff": row[3]}}])
        connection.close()
    else:
        lines = plan.get("dump", [])
        for _, result in lines:
            if result and "{{LOG_DIR}}" in (result.get("output") or ""):
                import tempfile
                words = json.loads((control / "test-command.json").read_text())
                log_dir = tempfile.mkdtemp(dir=words[4])
                pathlib.Path(log_dir, "test-run-report.txt").write_text(result["output"])
                result["output"] = result["output"].replace("{{LOG_DIR}}", log_dir)
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
    for tool in ("cosmic-ray", "cr-filter-git", "cr-filter-pragma", "cr-filter-lines", "python"):
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
    # A temporary directory of the case's own, so what the script leaves there is the case's to
    # see, and is removed with the case.
    temporary_directory = control / "temporary-directory"
    temporary_directory.mkdir(exist_ok=True)
    environment["TMPDIR"] = str(temporary_directory)
    environment.update(extra_environment or {})
    # The full mutation pass, unless the case names a pass: it mutates every changed line.
    passes = (load_script_module().QUICK_MUTATION_PASS_COMMAND_LINE_FLAG,
              load_script_module().FULL_MUTATION_PASS_COMMAND_LINE_FLAG,
              load_script_module().RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG)
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

# As cosmic-ray 8.7.0 writes it for HEAD_FILES' scripts/thing.py: no newline after the last
# context line, which is the empty line after the file's last newline.
SURVIVOR_DIFF = ("--- mutation diff ---\n--- a/scripts/thing.py\n+++ b/scripts/thing.py\n"
                 "@@ -1,3 +1,3 @@\n def double(x):\n-    return x + x\n+    return x * x\n ")


def runner_output_with_suites_timed_out(timed_out, others=()):
    """What the suite runner prints when each (suite, limit) of timed_out ran past its limit.

    Its lines come from the runner's own code, so a case follows the runner's format."""
    runner = load_test_suite_runner()
    results = [{"suite": suite, "exit": -9, "seconds": limit + 1.0, "skips": [],
                "timeout": {"limit": limit, "recorded": None}} for suite, limit in timed_out]
    lines = ["scripts/run-all-test-suites.py: /tmp/worktree at abc (tracked files match that commit)"]
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


def runner_output_with_a_suite_failed_with_exit_code(suite, exit_code, out_of_memory=None):
    """The suite runner's FAIL lines for a suite that ended with this exit code, from its code.

    out_of_memory, when given, is the result's "out of memory" entry: the kernel killed
    processes of the suite at its memory ceiling."""
    runner = load_test_suite_runner()
    failed = {"suite": suite, "exit": exit_code, "seconds": 1.0, "skips": [],
              **({"out of memory": out_of_memory} if out_of_memory else {})}
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
             "60.0", str(scratch), sys.executable, str(SCRIPT.with_name("run-all-test-suites.py")),
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


def run_recorded_mutant_killed_check(scratch_name, head_files, diff_text, *flags,
                                     origin_main_files=None, before_run=None,
                                     extra_environment=None, more_diff_texts=()):
    """Run --recorded-mutant-killed-check on a scratch repository holding head_files, given
    mutant.diff holding diff_text, then mutant-2.diff and on holding more_diff_texts.

    With origin_main_files, refs/remotes/origin/main names a commit on the base holding them.
    before_run, given the repository, runs just before the check.
    The suites are real fixture suites, run by the real suite runner; no cosmic-ray is given."""
    survivors = load_script_module()
    repository, base, head = scratch_repository(scratch_name, head_files)
    if origin_main_files is not None:
        git(repository, "checkout", "-q", "--detach", base)
        for path, text in origin_main_files.items():
            (repository / path).parent.mkdir(parents=True, exist_ok=True)
            (repository / path).write_text(text)
        git(repository, "add", "-A")
        git(repository, "commit", "-q", "-m", "origin main")
        git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(repository, "checkout", "-q", "main")
    control = Path(scratch_name) / "control"
    control.mkdir()
    diff_file = Path(scratch_name) / "mutant.diff"
    if diff_text is not None:
        diff_file.write_text(diff_text)
    diff_files = [str(diff_file)]
    for number, text in enumerate(more_diff_texts, start=2):
        diff_files.append(str(Path(scratch_name) / f"mutant-{number}.diff"))
        Path(diff_files[-1]).write_text(text)
    worktrees_before = worktrees_of(repository)
    if before_run is not None:
        before_run(repository)
    completed = run_script(repository, control,
                           survivors.RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG,
                           *diff_files, *flags, extra_environment=extra_environment)
    return completed, repository, worktrees_before, head


def run_recorded_mutant_killed_check_cases():
    survivors = load_script_module()
    runner = load_test_suite_runner()
    killing_test = ("import importlib.util, sys\n"
                    "spec = importlib.util.spec_from_file_location('thing', 'scripts/thing.py')\n"
                    "thing = importlib.util.module_from_spec(spec)\n"
                    "spec.loader.exec_module(thing)\n"
                    "sys.exit(0 if thing.double(3) == 6 else 1)\n")
    killing_files = {**HEAD_FILES, "scripts/thing-test.py": killing_test}
    killed_line = f"\n{survivors.MUTANT_KILLED_LINE_PREFIX}: "
    survived_line = f"\n{survivors.MUTANT_SURVIVED_LINE_PREFIX}: "
    no_longer_exists_line = f"\n{survivors.MUTANT_NO_LONGER_EXISTS_LINE_PREFIX}: "
    could_not_be_judged_line = f"\n{survivors.MUTANT_COULD_NOT_BE_JUDGED_LINE_PREFIX}: "

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, repository, worktrees_before, head = run_recorded_mutant_killed_check(
            scratch_name, killing_files, SURVIVOR_DIFF)
        last = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
        check("the recorded mutant killed check exits 0 with a MUTANT KILLED line naming the "
              "diff file and the head, and a last line counting 1 killed, when a suite at the "
              "head fails with the mutant applied",
              completed.returncode == 0
              and f"{killed_line}{Path(scratch_name) / 'mutant.diff'}: at head {head[:12]}"
                  in "\n" + completed.stdout
              and last == f"RECORDED MUTANTS at head {head[:12]}: 1 killed, 0 survived, "
                          f"0 no longer exist, 0 could not be judged",
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
        check("the recorded mutant killed check removes its scratch worktree, and leaves the "
              "checkout's file unmutated",
              worktrees_of(repository) == worktrees_before
              and (repository / "scripts/thing.py").read_text() == HEAD_FILES["scripts/thing.py"],
              worktrees_of(repository))

    # The suite's run without the mutant leaves bytecode that Python takes without checking the
    # source, as a cache whose size and whole-second mtime the mutant leaves the same would be
    # taken; only removing the scratch worktree's caches lets the mutated run see the mutant.
    stale_cache_test = ("import importlib.util, py_compile, sys\n"
                        "from pathlib import Path\n"
                        "cache = importlib.util.cache_from_source('scripts/thing.py')\n"
                        "if not Path(cache).exists():\n"
                        "    py_compile.compile('scripts/thing.py', cfile=cache, doraise=True,\n"
                        "        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)\n"
                        + killing_test.split("\n", 1)[1])
    # The signal-sandbox runner's --mutant run sets PYTHONPYCACHEPREFIX for this file's suite.
    for prefix_note, with_prefix in (("", False), (", with PYTHONPYCACHEPREFIX inherited", True)):
        with tempfile.TemporaryDirectory() as scratch_name:
            completed, _, _, _ = run_recorded_mutant_killed_check(
                scratch_name, {**HEAD_FILES, "scripts/thing-test.py": stale_cache_test},
                SURVIVOR_DIFF,
                extra_environment=({"PYTHONPYCACHEPREFIX": str(Path(scratch_name) / "bytecode")}
                                   if with_prefix else None))
            check("the recorded mutant killed check removes the scratch worktree's bytecode "
                  "caches before the run with the mutant, so a cache the run without it left "
                  "cannot hide the mutant" + prefix_note,
                  completed.returncode == 0 and killed_line in "\n" + completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # The variable's name sorts before PYTHONPYCACHEPREFIX, as PATH and HOME do.
    environment_test = ("import os, sys\n"
                        "sys.exit(0 if os.environ.get('MUTANT_SUITE_SEES_THIS') == '1' else 1)\n")
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**HEAD_FILES, "scripts/thing-test.py": environment_test},
            SURVIVOR_DIFF, extra_environment={
                "PYTHONPYCACHEPREFIX": str(Path(scratch_name) / "bytecode"),
                "MUTANT_SUITE_SEES_THIS": "1"})
        check("the recorded mutant killed check drops only PYTHONPYCACHEPREFIX from the "
              "environment it gives the suites: a suite that needs another variable passes "
              "without the mutant, and survives it",
              completed.returncode == 1 and survived_line in "\n" + completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # double(2) is 4 under x + x and x * x alike, and 0 under x - x.
    surviving_test_files = {**HEAD_FILES, "scripts/thing-test.py":
                            killing_test.replace("double(3) == 6", "double(2) == 4")}
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, surviving_test_files, SURVIVOR_DIFF)
        check("the recorded mutant killed check exits 1 with a MUTANT SURVIVED line, and says to "
              "write a test, when every suite passes with the mutant applied",
              completed.returncode == 1 and survived_line in "\n" + completed.stdout
              and "Write or change a test that fails with each surviving mutant"
                  in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    subtracting_diff = SURVIVOR_DIFF.replace("x * x", "x - x")
    with tempfile.TemporaryDirectory() as scratch_name:
        verdicts_file = Path(scratch_name) / "verdicts.json"
        completed, repository, worktrees_before, head = run_recorded_mutant_killed_check(
            scratch_name, surviving_test_files, SURVIVOR_DIFF,
            "--recorded-mutant-killed-check-verdicts-json-file-to-write", str(verdicts_file),
            more_diff_texts=[subtracting_diff])
        first, second = (str(Path(scratch_name) / "mutant.diff"),
                         str(Path(scratch_name) / "mutant-2.diff"))
        verdict_lines = [line for line in completed.stdout.splitlines()
                         if line.startswith("MUTANT ")]
        written = json.loads(verdicts_file.read_text()) if verdicts_file.exists() else {}
        check("two recorded mutants in one command: a line for each in the order given, one "
              "survived and one killed, exit 1, both counted, the verdicts written to the JSON "
              "file, the worktree removed and the checkout's file unmutated",
              completed.returncode == 1
              and [line.split(": ")[:2] for line in verdict_lines]
                  == [[survivors.MUTANT_SURVIVED_LINE_PREFIX, first],
                      [survivors.MUTANT_KILLED_LINE_PREFIX, second]]
              and "1 killed, 1 survived, 0 no longer exist, 0 could not be judged" in completed.stdout
              and written.get("head") == head
              and {name: verdict["verdict"] for name, verdict
                   in written.get("verdicts", {}).items()} == {first: "survived",
                                                               second: "killed"}
              and written["verdicts"][second]["why"].startswith(f"at head {head[:12]}")
              and worktrees_of(repository) == worktrees_before
              and (repository / "scripts/thing.py").read_text() == HEAD_FILES["scripts/thing.py"],
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr} "
              f"json={written}")

    with tempfile.TemporaryDirectory() as scratch_name:
        verdicts_file = Path(scratch_name) / "verdicts.json"
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, killing_files, None,
            "--recorded-mutant-killed-check-verdicts-json-file-to-write", str(verdicts_file),
            more_diff_texts=[SURVIVOR_DIFF])
        written = json.loads(verdicts_file.read_text()) if verdicts_file.exists() else {}
        check("a diff file that cannot be read beside one that can: the readable mutant is "
              "judged killed, the other could not be judged, exit 2, and both are in the JSON file",
              completed.returncode == 2
              and f"{could_not_be_judged_line}{Path(scratch_name) / 'mutant.diff'}: the diff file cannot "
                  f"be read" in "\n" + completed.stdout
              and killed_line in "\n" + completed.stdout
              and [verdict["verdict"] for verdict in written.get("verdicts", {}).values()]
                  == ["could not be judged", "killed"],
              f"rc={completed.returncode} out={completed.stdout} json={written}")

    with tempfile.TemporaryDirectory() as scratch_name:
        verdicts_file = Path(scratch_name) / "not-a-directory" / "verdicts.json"
        (Path(scratch_name) / "not-a-directory").write_text("")
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, killing_files, SURVIVOR_DIFF,
            "--recorded-mutant-killed-check-verdicts-json-file-to-write", str(verdicts_file))
        check("a verdicts JSON file that cannot be written exits 2, saying the lines above are "
              "the whole result",
              completed.returncode == 2 and killed_line in "\n" + completed.stdout
              and "the verdicts were not written to" in completed.stderr,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, repository, worktrees_before, head = run_recorded_mutant_killed_check(
            scratch_name, {**HEAD_FILES, "scripts/thing-test.py": "import sys\nsys.exit(1)\n"},
            SURVIVOR_DIFF)
        check("the recorded mutant killed check exits 2 when the suites fail without the "
              "mutant, naming the head, and removes its worktree",
              completed.returncode == 2
              and f"do not pass at head {head[:12]} without a mutant" in completed.stderr
              and "without a mutant" in completed.stderr
              and worktrees_of(repository) == worktrees_before,
              f"rc={completed.returncode} err={completed.stderr}")

    for case_name, thing_source in [
        ("the line ends with the pragma", "def double(x):\n    return x + x  # pragma: no mutate\n"),
        ("the line ends with the pragma, and the same line without it is elsewhere in the file",
         "def double(x):\n    return x + x  # pragma: no mutate, x * x differs\n\n\n"
         "def twice(x):\n    return x + x\n"),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            completed, _, _, _ = run_recorded_mutant_killed_check(
                scratch_name, {**killing_files, "scripts/thing.py": thing_source}, SURVIVOR_DIFF)
            check(f"a recorded mutant whose line at the head ends with a `# pragma: no mutate` "
                  f"comment no longer exists, exit 0: {case_name}",
                  completed.returncode == 0
                  and f"{no_longer_exists_line}{Path(scratch_name) / 'mutant.diff'}: the line it changes in "
                      f"scripts/thing.py ends with a `# pragma: no mutate` comment"
                      in "\n" + completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**HEAD_FILES, "scripts/thing.py":
                           "def double(x):\n    return x + x\n\n\n"
                           "def twice(x):\n    return x + x  # pragma: no mutate\n"},
            SURVIVOR_DIFF)
        check("a recorded mutant whose own line has no `# pragma: no mutate` comment is still "
              "judged when the same line elsewhere in the file has one: it survives, exit 1",
              completed.returncode == 1 and survived_line in "\n" + completed.stdout
              and no_longer_exists_line not in "\n" + completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # A later change edited the context line, so only the replaced line is looked for; read
    # without the pragma it is in both functions, read exactly only in twice(), which no suite
    # tests, so applying it there would make the mutant survive.
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**killing_files, "scripts/thing.py":
                           "def double(x):\n    # doubled\n    return x + x  # pragma: no mutate\n"
                           "\n\ndef twice(x):\n    return x + x\n"},
            SURVIVOR_DIFF)
        check("a recorded mutant whose replaced line appears at the head both with and without "
              "a `# pragma: no mutate` comment, its context line edited, could not be judged, "
              "exit 2, and is not applied at the untagged twin",
              completed.returncode == 2
              and f"{could_not_be_judged_line}{Path(scratch_name) / 'mutant.diff'}: in "
                  f"scripts/thing.py at head" in "\n" + completed.stdout
              and "which copy is the mutant's own line cannot be told" in completed.stdout
              and survived_line not in "\n" + completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # Neither scripts/gone.py nor a suite for it is at the head, as after a deletion.
    for case_name, origin_main_files, wanted_line, wanted_exit in [
        ("origin/main lacks it too, so the mutant no longer exists, exit 0", {"OTHER": "x\n"},
         no_longer_exists_line, 0),
        ("origin/main still has it, so it could not be judged, exit 2",
         {"scripts/gone.py": HEAD_FILES["scripts/thing.py"]}, could_not_be_judged_line, 2),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            completed, _, _, _ = run_recorded_mutant_killed_check(
                scratch_name, killing_files, SURVIVOR_DIFF.replace("thing.py", "gone.py"),
                origin_main_files=origin_main_files)
            check(f"a recorded mutant whose file and suites are gone from the head is judged by "
                  f"whether it still exists before whether a suite reads it: {case_name}",
                  completed.returncode == wanted_exit
                  and f"{wanted_line}{Path(scratch_name) / 'mutant.diff'}: " in "\n" + completed.stdout
                  and "no recorded suite reads" not in completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        import fcntl
        lock_file = Path(scratch_name) / "machine.lock"
        with open(lock_file, "a+") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            holder.write("pid 7, the holder in this test\n")
            holder.flush()
            completed, repository, worktrees_before, head = run_recorded_mutant_killed_check(
                scratch_name, killing_files, SURVIVOR_DIFF, "--lock-file", str(lock_file),
                extra_environment={runner.SIGNAL_SANDBOX_INSIDE_VARIABLE: "1"})
        check("the recorded mutant killed check exits 2 when the suite runner, run without a "
              "mutant, is refused the machine's lock: it says the runner judged no suite and "
              "prints the refusal, not that the suites fail, and removes its worktree",
              completed.returncode == 2
              and f"the suite runner scripts/run-all-test-suites.py, run at head {head[:12]} "
                  f"without a mutant, exited {runner.EXIT_LOCKED}, which means it ran no suite"
                  in completed.stderr
              and "pid 7, the holder in this test" in completed.stderr
              and "do not pass" not in completed.stderr
              and "MUTANT " not in completed.stdout
              and worktrees_of(repository) == worktrees_before,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, repository, worktrees_before, head = run_recorded_mutant_killed_check(
            scratch_name, killing_files, SURVIVOR_DIFF,
            "--python", str(Path(scratch_name) / "no-such-python"))
        check("the recorded mutant killed check exits 2 when the suite runner, run without a "
              "mutant, ends nonzero without reporting a suite as failed: it says so and prints "
              "the runner's output, not that the suites fail",
              completed.returncode == 2
              and f"the suite runner scripts/run-all-test-suites.py, run at head {head[:12]} "
                  f"without a mutant, exited " in completed.stderr
              and "without reporting any suite as failed" in completed.stderr
              and "do not pass" not in completed.stderr
              and worktrees_of(repository) == worktrees_before,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # scripts/gone.py is not at the head, but its sibling suite is, so its mutant gets as far as
    # reading the file.
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**killing_files, "scripts/gone-test.py": "import sys\nsys.exit(0)\n"},
            SURVIVOR_DIFF.replace("thing.py", "gone.py"), more_diff_texts=[SURVIVOR_DIFF])
        check("a recorded mutant whose file cannot be read at the head could not be judged, "
              "saying why, and the next mutant is still judged",
              completed.returncode == 2
              and f"{could_not_be_judged_line}{Path(scratch_name) / 'mutant.diff'}: it does not "
                  f"apply to scripts/gone.py at head" in "\n" + completed.stdout
              and "the file cannot be read" in completed.stdout
              and f"{killed_line}{Path(scratch_name) / 'mutant-2.diff'}: "
                  in "\n" + completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**killing_files,
                           "scripts/thing.py": "def double(x):\n    # doubled\n    return x + x\n"},
            SURVIVOR_DIFF)
        check("a recorded mutant whose context line a later change edited is applied where its "
              "replaced line appears once, and judged",
              completed.returncode == 0 and killed_line in "\n" + completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, repository, worktrees_before, _ = run_recorded_mutant_killed_check(
            scratch_name, {**killing_files,
                           "scripts/thing.py": "def double(x):\n    return 2 * x\n"},
            SURVIVOR_DIFF)
        check("the recorded mutant killed check exits 2 with a MUTANT COULD NOT BE JUDGED line when the "
              "mutant's diff does not apply at the head, and removes its worktree",
              completed.returncode == 2
              and f"{could_not_be_judged_line}{Path(scratch_name) / 'mutant.diff'}: it does not apply to "
                  f"scripts/thing.py" in "\n" + completed.stdout
              and worktrees_of(repository) == worktrees_before,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    branch_changed_files = {**killing_files, "scripts/thing.py": "def double(x):\n    return 2 * x\n"}
    for case_name, origin_main_files, wanted_line, wanted, wanted_exit in [
        ("the lines are gone from origin/main too, so it no longer exists, exit 0",
         {"scripts/thing.py": "def double(x):\n    return 2 * x\n"}, no_longer_exists_line,
         "gone from origin/main too, so there is nothing to kill; the nightly mutation pass "
         "drops it from its task", 0),
        ("origin/main has no such file, so it no longer exists, exit 0", {"OTHER": "x\n"}, no_longer_exists_line,
         "gone from origin/main too, so there is nothing to kill", 0),
        ("origin/main still has the lines, so it says the branch changed them, exit 2",
         {"scripts/thing.py": HEAD_FILES["scripts/thing.py"]}, could_not_be_judged_line,
         "origin/main still has the lines it replaces, so your branch changed them.\n"
         "If your branch changed them on purpose", 2),
        ("origin/main changed only a context line beside the replaced line, so it still has the "
         "replaced line and the branch changed it, exit 2",
         {"scripts/thing.py": "def double(x):\n    # doubled\n    return x + x\n"},
         could_not_be_judged_line, "so your branch changed them", 2),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            completed, _, _, _ = run_recorded_mutant_killed_check(
                scratch_name, branch_changed_files, SURVIVOR_DIFF,
                origin_main_files=origin_main_files)
            check(f"a recorded mutant that does not apply at the head: {case_name}",
                  completed.returncode == wanted_exit and wanted_line in "\n" + completed.stdout
                  and wanted in completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
    cannot_tell = "whether origin/main still has the lines it replaces cannot be told"

    def origin_main_file_unreadable(repository):
        blob = git(repository, "rev-parse", "refs/remotes/origin/main:scripts/thing.py").strip()
        (repository / ".git" / "objects" / blob[:2] / blob[2:]).unlink()

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, branch_changed_files, SURVIVOR_DIFF, origin_main_files={
                "scripts/thing.py": "def double(x):\n    return x + x\n# on main only\n"},
            before_run=origin_main_file_unreadable)
        check("a recorded mutant that does not apply at the head, where git cannot read "
              "origin/main's file: it could not be judged, and says why",
              completed.returncode == 2 and no_longer_exists_line not in "\n" + completed.stdout
              and cannot_tell in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    def origin_main_scripts_tree_unreadable(repository):
        tree = git(repository, "rev-parse", "refs/remotes/origin/main:scripts").strip()
        (repository / ".git" / "objects" / tree[:2] / tree[2:]).unlink()

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, branch_changed_files, SURVIVOR_DIFF, origin_main_files={
                "scripts/thing.py": "def double(x):\n    return x + x\n# on main only\n"},
            before_run=origin_main_scripts_tree_unreadable)
        check("a recorded mutant that does not apply at the head, where git cannot list "
              "origin/main's tree: it could not be judged, and says why",
              completed.returncode == 2 and no_longer_exists_line not in "\n" + completed.stdout
              and cannot_tell in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, branch_changed_files, SURVIVOR_DIFF)
        check("a recorded mutant that does not apply at the head, with no origin/main: it could "
              "not be judged, and says what to do",
              completed.returncode == 2 and cannot_tell in completed.stdout
              and "make sure your branch's head has scripts/thing.py as origin/main has it"
                  in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(scratch_name, killing_files, None)
        check("the recorded mutant killed check exits 2 when the diff file cannot be read",
              completed.returncode == 2 and "cannot be read" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, killing_files, "--- mutation diff ---\n@@ -1 +1 @@\n-a\n+b\n")
        check("the recorded mutant killed check exits 2 when the diff names no file",
              completed.returncode == 2 and "names no file to mutate or no change to make"
              in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {"scripts/thing.py": HEAD_FILES["scripts/thing.py"]}, SURVIVOR_DIFF)
        check("the recorded mutant killed check exits 2 when the mutated file has no suite",
              completed.returncode == 2 and "no recorded suite reads scripts/thing.py"
              in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    path, hunks = survivors.recorded_mutant_module_path_and_hunks(SURVIVOR_DIFF)
    check("a recorded mutant's diff names the file it changes, and its one hunk",
          path == "scripts/thing.py" and hunks == [
              (1, ["def double(x):", "    return x + x", ""],
               ["def double(x):", "    return x * x", ""])], (path, hunks))
    apply_mutant = survivors.source_with_recorded_mutant_applied
    source = HEAD_FILES["scripts/thing.py"]
    check("a recorded mutant applies at its own line, the file's last newline kept",
          apply_mutant(source, hunks) == "def double(x):\n    return x * x\n",
          apply_mutant(source, hunks))
    check("a recorded mutant whose lines the branch moved applies where they appear once",
          apply_mutant("import os\n\n" + source, hunks)
          == "import os\n\ndef double(x):\n    return x * x\n",
          apply_mutant("import os\n\n" + source, hunks))
    check("a recorded mutant whose context line changed applies where its replaced line appears "
          "once",
          apply_mutant("def double(y):\n    return x + x\n", hunks)
          == "def double(y):\n    return x * x\n",
          apply_mutant("def double(y):\n    return x + x\n", hunks))
    check("a recorded mutant whose lines appear twice away from its own line does not apply",
          apply_mutant("import os\n" + source + "\n" + source, hunks) is None)
    check("a recorded mutant whose lines are gone does not apply",
          apply_mutant("def double(x):\n    return 2 * x\n", hunks) is None)
    two_hunks = [(1, ["a"], ["A"]), (3, ["c"], ["C"])]
    check("a recorded mutant with two hunks applies both",
          apply_mutant("a\nb\nc\n", two_hunks) == "A\nb\nC\n", apply_mutant("a\nb\nc\n", two_hunks))

    # A context line of the mutant's own hunk carries the pragma; an exact twin of the hunk's
    # lines, without it, is in twice(). The mutant must be applied in double(), not in twice().
    twin_source = ("def double(x):\n    x = int(x)\n    y = x  # pragma: no mutate\n"
                   "    return y * 2\n    # end\n\n\ndef twice(x):\n    x = int(x)\n    y = x\n"
                   "    return y * 2\n    # end\n")
    twin_hunks = [(2, ["    x = int(x)", "    y = x", "    return y * 2", "    # end"],
                   ["    x = int(x)", "    y = x", "    return y + 2", "    # end"])]
    twin_verdict, twin_mutated = survivors.recorded_mutant_verdict_without_a_suite_run(
        None, "scripts/thing.py", twin_hunks, "0" * 40, twin_source, None, {})
    check("a recorded mutant whose hunk has an exact twin elsewhere in the file is applied at "
          "its own place, found reading a `# pragma: no mutate` comment as absent, and the "
          "context line keeps its comment",
          twin_verdict is None and twin_mutated == twin_source.replace(
              "x  # pragma: no mutate\n    return y * 2", "x  # pragma: no mutate\n    return y + 2"),
          (twin_verdict, twin_mutated))

    # Both hunks moved off their own lines, so each is found by its replaced line alone: the
    # second hunk's replaced line is the first hunk's context line, and their places overlap.
    overlap_source = "x\na\nb\nc\n"
    overlap_hunks = [(1, ["a", "b"], ["A", "b"]), (5, ["b", "c"], ["B", "c"])]
    overlap_verdict, overlap_mutated = survivors.recorded_mutant_verdict_without_a_suite_run(
        None, "scripts/thing.py", overlap_hunks, "0" * 40, overlap_source, None, {})
    check("a recorded mutant whose two hunks are found at overlapping places is not applied "
          "and could not be judged",
          overlap_mutated is None and overlap_verdict is not None
          and overlap_verdict[0] == "could not be judged" and "overlap" in overlap_verdict[1],
          (overlap_verdict, overlap_mutated))
    check("hunks at places that touch but do not overlap are not refused",
          not survivors.recorded_mutant_hunk_places_overlap([(0, ["a"], ["A"]), (1, ["b"], ["B"])]),
          "refused")

    verdict = survivors.recorded_mutant_run_verdict
    check("a run with the mutant applied that exits 0 is a survivor",
          verdict(0, "", runner) == ("survived", None), verdict(0, "", runner))
    check("a run with the mutant applied whose suite failed by its exit code is a kill",
          verdict(1, runner_output_with_a_suite_failed_with_exit_code(
              "scripts/thing-test.py", 1), runner) == ("killed", None))
    timed_out = verdict(1, runner_output_with_suites_timed_out(
        [("scripts/thing-test.py", 600)]), runner)
    check("a run with the mutant applied whose suite ran past its own limit is no verdict, "
          "naming the suite and the limit",
          timed_out[0] is None and "scripts/thing-test.py ran past its own limit of 600 s"
          in timed_out[1], timed_out)
    refused = verdict(3, f"{runner.PROGRAM}: not run — another run holds the lock\n", runner)
    check("a run with the mutant applied that the runner refused is no verdict, quoting the "
          "runner's refusal",
          refused[0] is None and "judged no suite failing" in refused[1]
          and "another run holds the lock" in refused[1], refused)

    completed = subprocess.run([sys.executable, str(SCRIPT),
                                survivors.RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG,
                                "x.diff", "--pull-request", "1"],
                               capture_output=True, text=True, check=False)
    check("--recorded-mutant-killed-check with --pull-request exits 2 and says why",
          completed.returncode == 2 and "not --pull-request or --base" in completed.stderr,
          completed.stderr)
    completed = subprocess.run([sys.executable, str(SCRIPT), "--full-mutation-pass"],
                               capture_output=True, text=True, check=False)
    check("a pass with neither --pull-request nor --head exits 2 and says one is required",
          completed.returncode == 2 and "--pull-request --head is required" in completed.stderr,
          completed.stderr)


def log_directories_left_in(control):
    """(the suite runner's own log directories, this script's log directories parents) left in
    the case's temporary directory, resolved as the script resolves the paths it prints."""
    temporary_directory = (control / "temporary-directory").resolve()
    return (sorted(temporary_directory.glob(f"{load_test_suite_runner().PROGRAM_FILE_NAME_STEM}-*")),
            sorted(temporary_directory.glob(
                f"{load_script_module().TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX}*")))


def run_test_suite_runner_log_directories_cases():
    survivors = load_script_module()
    killing_test = ("import importlib.util, sys\n"
                    "spec = importlib.util.spec_from_file_location('thing', 'scripts/thing.py')\n"
                    "thing = importlib.util.module_from_spec(spec)\n"
                    "spec.loader.exec_module(thing)\n"
                    "sys.exit(0 if thing.double(3) == 6 else 1)\n")
    # double(2) is 4 under x + x and x * x alike, so this mutant survives and x - x is killed.
    surviving_or_killing_test = killing_test.replace("double(3) == 6", "double(2) == 4")
    subtracting_diff = SURVIVOR_DIFF.replace("x * x", "x - x")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**HEAD_FILES, "scripts/thing-test.py": surviving_or_killing_test},
            SURVIVOR_DIFF, more_diff_texts=[subtracting_diff])
        runner_log_directories, parents = log_directories_left_in(Path(scratch_name) / "control")
        check("the recorded mutant killed check, judging one mutant killed and one survived, "
              "leaves no log directory of the suite runner's runs in the temporary directory",
              completed.returncode == 1
              and f"\n{survivors.MUTANT_SURVIVED_LINE_PREFIX}: " in "\n" + completed.stdout
              and f"\n{survivors.MUTANT_KILLED_LINE_PREFIX}: " in "\n" + completed.stdout
              and runner_log_directories == [] and parents == []
              and "are kept in" not in completed.stderr,
              f"left={runner_log_directories + parents} rc={completed.returncode} "
              f"out={completed.stdout} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        completed, _, _, _ = run_recorded_mutant_killed_check(
            scratch_name, {**HEAD_FILES, "scripts/thing-test.py": "import sys\nsys.exit(1)\n"},
            SURVIVOR_DIFF)
        runner_log_directories, parents = log_directories_left_in(Path(scratch_name) / "control")
        kept = sorted(parents[0].iterdir()) if len(parents) == 1 else []
        check("when the suites fail without a mutant, the recorded mutant killed check keeps "
              "that run's log directory, which holds the failing suite's log the refusal "
              "names, and names the directory it is kept in",
              completed.returncode == 2 and runner_log_directories == [] and len(kept) == 1
              and f" — log {kept[0]}/" in completed.stderr
              and f"are kept in {parents[0]};" in completed.stderr,
              f"left={runner_log_directories + parents} kept={kept} err={completed.stderr}")

    # The fake cosmic-ray's baseline runs the test command, so the suite runner runs for real.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"run_test_command": True, "dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
             killed_with_output("scripts/run-all-test-suites.py: worktree; logs in {LOG_DIR}\n"
                                + SUITE_FAILED_RUNNER_OUTPUT)],
            [work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Mul", "b"),
             killed_with_output("scripts/run-all-test-suites.py: worktree; logs in {LOG_DIR}\n"
                                "scripts/run-all-test-suites.py: not run to the end — stopped by SIGTERM\n")],
        ]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        runner_log_directories, parents = log_directories_left_in(control)
        kept = sorted(parents[0].iterdir()) if len(parents) == 1 else []
        check("a pass whose baseline the suite runner ran, with one mutant killed and one "
              "errored, leaves no log directory of the runner's own, keeps only the errored "
              "mutant's log directory, and names the directory it is kept in",
              completed.returncode == 1 and "1 killed" in completed.stdout
              and "1 errored" in completed.stdout and runner_log_directories == []
              and len(kept) == 1
              and "not run to the end" in (kept[0] / "test-run-report.txt").read_text()
              and f"are kept in {parents[0]};" in completed.stderr,
              f"left={runner_log_directories + parents} kept={kept} "
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")


    # cosmic-ray, stopping a run at its own limit, records only "timeout": no log directory named.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"run_test_command": True, "dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
             killed_with_output(survivors.TIMED_OUT_OUTPUT)],
        ]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        runner_log_directories, parents = log_directories_left_in(control)
        kept = sorted(parents[0].iterdir()) if len(parents) == 1 else []
        check("a pass with a mutant cosmic-ray recorded only as \"timeout\", whose output names "
              "no log directory, keeps every log directory of that file and names where",
              "1 errored" in completed.stdout and len(kept) == 1
              and f"are kept in {parents[0]};" in completed.stderr,
              f"left={runner_log_directories + parents} kept={kept} "
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

def run_recorded_mutant_could_not_be_judged_log_directory_kept_case():
    survivors = load_script_module()
    runner = load_test_suite_runner()
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, _, head = scratch_repository(scratch_name, HEAD_FILES)
        parent = Path(scratch_name) / "log-directories-parent"
        parent.mkdir()
        real_run = subprocess.run
        runs = []

        # The run without a mutant passes; the run with it exits 3 judging no suite failing.
        def suite_runner_run(command, *args, **kwargs):
            if "--log-dir" not in command:
                return real_run(command, *args, **kwargs)
            log_dir = Path(command[command.index("--log-dir") + 1])
            (log_dir / "test-run-report.txt").write_text("stopped\n")
            runs.append(log_dir)
            return subprocess.CompletedProcess(
                command, 0 if len(runs) == 1 else 3,
                stdout="" if len(runs) == 1 else "scripts/run-all-test-suites.py: not run to the end\n")
        real_verdict = survivors.recorded_mutant_verdict_without_a_suite_run
        survivors.recorded_mutant_verdict_without_a_suite_run = \
            lambda checkout, path, hunks, head, source, why, environment: (None, source)
        subprocess.run = suite_runner_run
        try:
            verdicts = survivors.recorded_mutants_judged_in_one_worktree(
                [("mutant.diff", "scripts/thing.py", [], ["scripts/thing-test.py"])], head,
                types.SimpleNamespace(python=sys.executable, lock_file=None), repository,
                dict(os.environ), runner, Path(scratch_name) / "recordings", parent)
        finally:
            subprocess.run = real_run
            survivors.recorded_mutant_verdict_without_a_suite_run = real_verdict
        check("a recorded mutant that could not be judged keeps its run's log directory, and the "
              "passing run without a mutant does not keep its own",
              verdicts.get("mutant.diff", ("",))[0] == "could not be judged"
              and len(runs) == 2 and not runs[0].exists() and runs[1].exists(),
              f"verdicts={verdicts} runs={runs} left={sorted(parent.iterdir())}")

def run_log_directories_parent_retention_and_stop_signal_cases():
    survivors = load_script_module()
    prefix = survivors.TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX
    now = time.time()
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        old, fresh, other = scratch / f"{prefix}old", scratch / f"{prefix}fresh", scratch / "other-old"
        for each in (old, fresh, other):
            (each / "a-log-dir").mkdir(parents=True)
        three_days_ago = now - 3 * 24 * 3600
        for each in (old, other):
            os.utime(each, (three_days_ago, three_days_ago))
        survivors.test_suite_runner_log_directories_parents_past_retention_removed(scratch, now)
        check("at start, a log directories parent an earlier run left more than two days ago is "
              "removed, and a fresh one and a directory of another name are left",
              not old.exists() and fresh.exists() and other.exists(),
              sorted(p.name for p in scratch.iterdir()))

    with tempfile.TemporaryDirectory() as scratch_name:
        parent = Path(scratch_name) / f"{prefix}stopped"
        (parent / "a-mutant-log-dir").mkdir(parents=True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            survivors.test_suite_runner_log_directories_parent_removed_or_named_as_kept(
                parent, stopped_by_signal=True)
        check("on a stop signal the log directories parent is removed with the log directories "
              "it still holds, and nothing is printed",
              not parent.exists() and err.getvalue() == "", err.getvalue())

    sessions_kept = ["--cosmic-ray-sessions-directory-kept-to-resume", "sessions"]
    for code, extra, stopped in ((128 + signal.SIGTERM, [], True), (128 + signal.SIGHUP, [], True),
                                 (2, [], False), (128 + signal.SIGTERM, sessions_kept, False)):
        with tempfile.TemporaryDirectory() as scratch_name:
            left_by_an_earlier_run = Path(scratch_name) / f"{prefix}earlier"
            (left_by_an_earlier_run / "a-log-dir").mkdir(parents=True)
            os.utime(left_by_an_earlier_run, (now - 3 * 24 * 3600, now - 3 * 24 * 3600))

            def raising(arguments, checkout, runner, environment, log_directories_parent):
                (log_directories_parent / "a-mutant-log-dir").mkdir()
                raise SystemExit(code)
            real = (survivors.quick_or_full_mutation_pass_or_recorded_mutant_killed_check,
                    survivors.load_test_suite_runner, tempfile.tempdir)
            survivors.quick_or_full_mutation_pass_or_recorded_mutant_killed_check = raising
            survivors.load_test_suite_runner = lambda: types.SimpleNamespace(
                launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed=dict)
            tempfile.tempdir = scratch_name
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    survivors.main_with_stop_signals_raising_system_exit(
                        ["--quick-mutation-pass", "--head", "HEAD", "--base", "HEAD", *extra])
                raised = None
            except SystemExit as exit_:
                raised = exit_.code
            finally:
                (survivors.quick_or_full_mutation_pass_or_recorded_mutant_killed_check,
                 survivors.load_test_suite_runner, tempfile.tempdir) = real
            left = list(Path(scratch_name).glob(f"{prefix}*"))
            kept_line = survivors.TEST_SUITE_RUNNER_LOGS_KEPT_LINE_PREFIX in err.getvalue()
            check(f"exit {code} out of the pass{' with kept sessions' if extra else ''}: a log "
                  f"directories parent an earlier run left three days ago is removed at start, "
                  f"and the log directories this run holds are "
                  + ("removed, with no line naming them" if stopped
                     else "kept, and one line names where"),
                  raised == code and not left_by_an_earlier_run.exists()
                  and (left == [] and not kept_line if stopped
                       else len(left) == 1 and kept_line),
                  f"raised={raised} left={left} err={err.getvalue()}")


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
    # cosmic-ray 8.7.0's cr-filter-pragma skips a mutation when its LAST line carries the
    # pragma, or the line before when the mutation ends at a line's start; the survivor
    # task names "line", so "line" must be that line.
    pragma_lines = [
        survivors.mutant_description(
            {"mutations": [{"module_path": "scripts/thing.py", "operator_name": "core/AddNot",
                            "start_pos": start, "end_pos": end}]}, {})["line"]
        for start, end in (([10, 7], [11, 12]), ([10, 4], [12, 0]), ([10, 4], [10, 9]))]
    check("a mutant's line is the line cr-filter-pragma reads: its last line, or the line "
          "before when it ends at a line's start, not its first line",
          pragma_lines == [11, 11, 10], pragma_lines)
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, _, _ = scratch_repository(scratch_name, QUICK_HEAD_FILES)
        old_head, new_head = commit_on_top(
            repository, "scripts/handler.py",
            HANDLER_SOURCE.replace("    return x + x\n", "    return 2 * x\n").replace(
                "        return -1\n", "        return -2\n        # and more\n"))
        changed = survivors.line_numbers_at_head_of_lines_changed_since_merge_base(repository, old_head, new_head,
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
              and "--survived-and-errored-mutants-json-file naming a path" in completed.stderr,
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
              and "scripts/broken.py at the head commit is not valid Python" in completed.stderr
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
              "Python", "latin.py at the head commit is not valid Python" in refused, refused)

    # Every listed repository-wide check is a suite in this repository.
    repository_root = SCRIPT.resolve().parent.parent
    missing = [suite for suite in survivors.REPOSITORY_WIDE_CHECKS
               if not (repository_root / suite).is_file()]
    check("every suite REPOSITORY_WIDE_CHECKS names exists, so a renamed check is not "
          "silently kept in the quick mutation pass", missing == [], missing)


# cosmic-ray's modules that the parallel workers import, faked: the session is a JSON file, and
# each mutation's operator name says what its worker does.
FAKE_COSMIC_RAY_PACKAGE = {
    "__init__.py": "",
    "config.py": """
import json, types
def load_config(path):
    return types.SimpleNamespace(**json.loads(open(path).read()))
""",
    "work_item.py": """
import enum, types
class WorkerOutcome(enum.Enum):
    NORMAL = "normal"
    EXCEPTION = "exception"
class TestOutcome(enum.Enum):
    SURVIVED = "survived"
    KILLED = "killed"
def WorkResult(**fields):
    return types.SimpleNamespace(**fields)
def MutationSpec(**fields):
    return types.SimpleNamespace(**fields)
""",
    "work_db.py": """
import enum, json, types
class WorkDB:
    class Mode(enum.Enum):
        open = 1
    def __init__(self, path, mode):
        self.path = path
        self.data = json.loads(open(path).read())
    @property
    def pending_work_items(self):
        return tuple(types.SimpleNamespace(job_id=item["job_id"], mutations=[
            types.SimpleNamespace(**dict(mutation, start_pos=tuple(mutation["start_pos"]),
                                         end_pos=tuple(mutation["end_pos"])))
            for mutation in item["mutations"]])
            for item in self.data["items"] if item["job_id"] not in self.data["results"])
    def set_result(self, job_id, result):
        self.data["results"][job_id] = {
            "worker_outcome": result.worker_outcome.value, "output": result.output,
            "test_outcome": None if result.test_outcome is None else result.test_outcome.value,
            "diff": result.diff}
        open(self.path, "w").write(json.dumps(self.data))
    def close(self):
        pass
""",
    "mutating.py": """
import os, sys
import time
from cosmic_ray.work_item import TestOutcome, WorkerOutcome, WorkResult
def mutate_and_test(mutations, test_command, timeout):
    operator = mutations[0].operator_name
    if operator == "worker-exits-3":
        print("first line", file=sys.stderr)
        print("last line", file=sys.stderr)
        sys.exit(3)
    if operator == "worker-prints-no-json":
        print("not JSON")
    if operator == "slow":
        time.sleep(2)
    if operator == "runs-15-seconds":
        time.sleep(15)
    return WorkResult(worker_outcome=WorkerOutcome.NORMAL,
                      output=f"{os.getcwd()} {test_command} {timeout}",
                      test_outcome=TestOutcome.KILLED, diff=f"diff of {operator}")
""",
}


def run_parallel_mutant_workers_with_fake_cosmic_ray_package(
        scratch_name, operators, worktree_names, job_ids_to_run="all",
        no_mutant_started_after="never"):
    """Run the parallel workers on a fake session whose work items have these operators; return
    (the run, the session as it was left, the worktrees)."""
    scratch = Path(scratch_name)
    package = scratch / "site" / "cosmic_ray"
    package.mkdir(parents=True)
    for name, text in FAKE_COSMIC_RAY_PACKAGE.items():
        (package / name).write_text(text)
    worktrees = [scratch / name for name in worktree_names]
    for worktree in worktrees:
        if not worktree.name.startswith("missing"):
            worktree.mkdir()
    config = scratch / "config.json"
    config.write_text(json.dumps({"test_command": "run the suites", "timeout": 12.5}))
    session = scratch / "session.json"
    session.write_text(json.dumps({"results": {}, "items": [
        {"job_id": f"job-{number}", "mutations": [dict(
            work_item("scripts/thing.py", 2, operator, "")["mutations"][0],
            definition_name=None)]}
        for number, operator in enumerate(operators)]}))
    completed = subprocess.run(
        [sys.executable, str(SCRIPT),
         load_script_module().COSMIC_RAY_SESSION_PENDING_MUTANTS_RUN_BY_PARALLEL_WORKERS_FLAG,
         str(config), str(session), job_ids_to_run, no_mutant_started_after,
         *map(str, worktrees)],
        capture_output=True, text=True, check=False, timeout=120,
        env={**os.environ, "PYTHONPATH": str(scratch / "site")})
    return completed, json.loads(session.read_text()), worktrees


def run_parallel_mutant_workers_cases_with_fake_cosmic_ray_package():
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, session, worktrees = run_parallel_mutant_workers_with_fake_cosmic_ray_package(
            scratch_name, ["first", "second", "third", "fourth"], ["one", "two"])
        outputs = [result["output"] for result in session["results"].values()]
        check("the parallel workers record a result for every pending mutant, each run in one "
              "of the worktrees with the config's test command and limit, and exit 0",
              completed.returncode == 0 and len(session["results"]) == 4
              and all(Path(output.split(" ")[0]).resolve() in
                      [worktree.resolve() for worktree in worktrees]
                      and output.endswith(" run the suites 12.5") for output in outputs)
              and session["results"]["job-1"]["diff"] == "diff of second",
              f"rc={completed.returncode} err={completed.stderr} session={session}")
    # Two mutants that each take two seconds, and two workers: each worker takes one before
    # either finishes, so each must have run in a worktree of its own.
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, session, worktrees = run_parallel_mutant_workers_with_fake_cosmic_ray_package(
            scratch_name, ["slow", "slow"], ["one", "two"])
        ran_in = sorted(str(Path(result["output"].split(" ")[0]).resolve())
                        for result in session["results"].values())
        check("mutants given to different workers run in different worktrees, one per worker",
              completed.returncode == 0
              and ran_in == sorted(str(worktree.resolve()) for worktree in worktrees),
              f"rc={completed.returncode} err={completed.stderr} ran_in={ran_in}")
    for case_name, operators, worktree_names, wanted in [
        ("a worker that exits nonzero", ["first", "worker-exits-3"], ["one", "two"],
         "work item job-1: the worker exited 3; it printed on standard error:\n"
         "      first line\n      last line\n"),
        ("a worker that prints no JSON", ["first", "worker-prints-no-json"], ["one"],
         "work item job-1: Expecting value"),
        ("a worker that cannot be started", ["first", "second"], ["missing-worktree"],
         "its worker could not be started (FileNotFoundError"),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            completed, session, _ = run_parallel_mutant_workers_with_fake_cosmic_ray_package(
                scratch_name, operators, worktree_names)
            started = worktree_names != ["missing-worktree"]
            check(f"{case_name}: exit 2, its mutant left with no result and named, and every "
                  f"other mutant recorded",
                  completed.returncode == 2 and wanted in completed.stderr
                  and "got no result, so they stay unrun in the session" in completed.stderr
                  and "job-1" not in session["results"]
                  and ("job-0" in session["results"]) == started,
                  f"rc={completed.returncode} err={completed.stderr} session={session}")
    with tempfile.TemporaryDirectory() as scratch_name:
        completed, session, _ = run_parallel_mutant_workers_with_fake_cosmic_ray_package(
            scratch_name, ["first", "second", "third", "fourth"], ["one", "two"],
            job_ids_to_run="job-1,job-3")
        check("given job ids, the parallel workers run those mutants only, the others left "
              "with no result, and exit 0",
              completed.returncode == 0 and sorted(session["results"]) == ["job-1", "job-3"],
              f"rc={completed.returncode} err={completed.stderr} session={session}")
    for case_name, operators, stop_after_seconds, wanted in [
            ("a time already come: no mutant is started", ["first", "second"], 0, 0),
            ("a time not yet come: every mutant is run", ["first", "second"], 600, 2),
            # One worker and two mutants of 15 seconds each: the first, started within the 10
            # seconds even on a busy machine, is running at the time.
            ("a time that comes while a mutant runs: that mutant is judged, and the next is "
             "not started", ["runs-15-seconds", "runs-15-seconds"], 10, 1)]:
        with tempfile.TemporaryDirectory() as scratch_name:
            completed, session, _ = run_parallel_mutant_workers_with_fake_cosmic_ray_package(
                scratch_name, operators, ["one"],
                no_mutant_started_after=repr(time.time() + stop_after_seconds))
            check(f"the parallel workers given the time after which no mutant starts, "
                  f"{case_name}; exit 0, with no mutant reported as without a worker's result",
                  completed.returncode == 0 and len(session["results"]) == wanted
                  and completed.stderr == "",
                  f"rc={completed.returncode} err={completed.stderr} session={session}")


def run_parallel_mutant_workers_case_with_real_cosmic_ray():
    venv = load_script_module().DEFAULT_COSMIC_RAY_VENV
    if not (venv / "bin" / "cosmic-ray").is_file():
        print(f"SKIP  [this machine cannot run it] the parallel workers with the real cosmic-ray: "
              f"no cosmic-ray venv at {venv}")
        return
    # The sibling suite kills a mutant of double() and no mutant of the unused triple().
    head_files = {"scripts/thing.py": "def double(x):\n    return x + x\n",
                  "scripts/thing-test.py": "import importlib.util, pathlib\n"
                  "spec = importlib.util.spec_from_file_location('thing', "
                  "pathlib.Path(__file__).with_name('thing.py'))\n"
                  "module = importlib.util.module_from_spec(spec)\n"
                  "spec.loader.exec_module(module)\n"
                  "assert module.double(3) == 6\nprint('all cases passed')\n"}
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, head_files)
        control = Path(scratch_name) / "control"
        control.mkdir()
        results = []
        # One worker: this case's suites take the machine lock, which a second worker's would be
        # refused.
        for flags in ([], ["--parallel-mutant-workers", "1"]):
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv), *flags)
            summary = [line for line in completed.stdout.splitlines()
                       if line.startswith("SUMMARY:")]
            survived = sorted(line for line in completed.stdout.splitlines()
                              if line.startswith("SURVIVED"))
            results.append((completed.returncode, summary, survived, completed.stderr))
        check("with the real cosmic-ray, the parallel worker judges every mutant as cosmic-ray "
              "exec does, and leaves no worktree",
              results[0][:3] == results[1][:3] and results[0][1]
              and " 0 errored, 0 not run" in results[0][1][0]
              and len(worktrees_of(repository)) == 1, results)


def mutants_with_a_result_in_kept_sessions(sessions):
    """(file, operator, line, occurrence, column) of each mutant with a result, other than one
    a filter skipped; two mutants of one operator on one line differ only by occurrence."""
    found = set()
    for session in sorted(Path(sessions).glob("*.sqlite")):
        connection = sqlite3.connect(session)
        found |= set(connection.execute(
            "SELECT module_path, operator_name, start_pos_row, occurrence, start_pos_col "
            "FROM mutation_specs JOIN "
            "work_results USING (job_id) WHERE worker_outcome != 'SKIPPED'"))
        connection.close()
    return found


def run_mutants_run_at_most_and_no_mutant_started_after_unix_time_cases():
    script = load_script_module()
    at_most_flag = script.MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG
    stop_flag = script.NO_MUTANT_STARTED_AFTER_UNIX_TIME_FLAG
    workers_flag = script.PARALLEL_MUTANT_WORKERS_FLAG
    kept_flag = script.COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG
    chosen = script.mutants_chosen_one_per_file_in_turn_in_order_seeded_by_head

    # ------------------------------------------------------------------
    # Which mutants are chosen.
    # ------------------------------------------------------------------
    twenty_files = {f"scripts/file-{number}.py": [("operator", line) for line in range(3)]
                    for number in range(20)}
    twelve = chosen(twenty_files, "head-a", 12)
    check("more files than mutants to choose: one mutant from each of 12 different files",
          len(twelve) == 12 and len({path for path, _ in twelve}) == 12
          and all(mutant in twenty_files[path] for path, mutant in twelve), twelve)
    few = {"scripts/one.py": [("a", 1)], "scripts/two.py": [("a", 1), ("b", 2)]}
    check("fewer mutants than the number to choose: every mutant is chosen, each once",
          sorted(chosen(few, "head-a", 12))
          == [("scripts/one.py", ("a", 1)), ("scripts/two.py", ("a", 1)),
              ("scripts/two.py", ("b", 2))], chosen(few, "head-a", 12))
    long_and_short = {"scripts/long.py": [("a", line) for line in range(100)],
                      "scripts/short.py": [("a", line) for line in range(10)]}
    shares = [path for path, _ in chosen(long_and_short, "head-a", 12)]
    check("a file of 10 mutants and a file of 100 are given 6 each of 12, in turn: the share "
          "is per file, not per mutant",
          shares.count("scripts/short.py") == 6 and shares.count("scripts/long.py") == 6
          and all(shares[index] != shares[index + 1] for index in range(0, 12, 2)), shares)
    one_short = {"scripts/long.py": [("a", line) for line in range(100)],
                 "scripts/short.py": [("a", 1)]}
    shares = [path for path, _ in chosen(one_short, "head-a", 6)]
    check("a file with no mutant left gives its turns to the others",
          shares.count("scripts/short.py") == 1 and shares.count("scripts/long.py") == 5
          and len(set(chosen(one_short, "head-a", 6))) == 6, shares)
    reordered = {path: list(reversed(twenty_files[path])) for path in reversed(twenty_files)}
    check("the same head chooses the same mutants in the same order, whatever order the files "
          "and their mutants are given in",
          chosen(twenty_files, "head-a", 12) == twelve
          and chosen(reordered, "head-a", 12) == twelve, chosen(reordered, "head-a", 12))
    check("another head chooses in another order", chosen(twenty_files, "head-b", 12) != twelve)
    check("a larger number chooses the same mutants first and then others, and 0 chooses none",
          chosen(twenty_files, "head-a", 30)[:12] == twelve
          and len(set(chosen(twenty_files, "head-a", 30))) == 30
          and chosen(twenty_files, "head-a", 0) == [], chosen(twenty_files, "head-a", 30))
    in_order = {"scripts/only.py": [("a", line) for line in range(50)]}
    check("the mutants of one file are chosen in a shuffled order, not the order they have in "
          "the file",
          chosen(in_order, "head-a", 50) != sorted(chosen(in_order, "head-a", 50))
          and chosen(in_order, "head-a", 50) != sorted(chosen(in_order, "head-a", 50),
                                                         reverse=True))
    check("the files take their turns in a shuffled order, not the order of their names",
          [path for path, _ in chosen(twenty_files, "head-a", 20)] != sorted(twenty_files)
          and [path for path, _ in chosen(twenty_files, "head-a", 20)]
          != sorted(twenty_files, reverse=True))
    same_mutants = {"scripts/a.py": [("a", line) for line in range(30)],
                    "scripts/b.py": [("a", line) for line in range(30)]}
    by_file = {path: [mutant for each, mutant in chosen(same_mutants, "head-a", 60)
                      if each == path] for path in same_mutants}
    check("two files with the same mutants have them chosen in different orders",
          by_file["scripts/a.py"] != by_file["scripts/b.py"], by_file)

    # ------------------------------------------------------------------
    # Bad invocations.
    # ------------------------------------------------------------------
    for flag, value in ((at_most_flag, "12"), (stop_flag, "1.5")):
        for case_name, others in [
                ("the quick pass", ["--quick-mutation-pass", "--cosmic-ray-venv", "/nowhere",
                                    workers_flag, "1", kept_flag, "/nowhere"]),
                ("no parallel workers", ["--full-mutation-pass", kept_flag, "/nowhere"]),
                ("no kept sessions", ["--full-mutation-pass", "--cosmic-ray-venv", "/nowhere",
                                      workers_flag, "1"])]:
            completed = subprocess.run([sys.executable, str(SCRIPT), *others, "--head", "a",
                                        "--base", "b", flag, value],
                                       capture_output=True, text=True, check=False)
            check(f"{flag} with {case_name} exits 2 and says what it needs",
                  completed.returncode == 2
                  and f"{flag} needs --full-mutation-pass, --parallel-mutant-workers"
                  in completed.stderr, completed.stderr)

    # ------------------------------------------------------------------
    # A full pass that runs some mutants and keeps the rest for a later run.
    # ------------------------------------------------------------------
    head_files = {}
    for name in ("a", "b", "c"):
        head_files[f"scripts/{name}.py"] = "def double(x):\n    return x + x\n"
        head_files[f"scripts/{name}-test.py"] = "import sys\nsys.exit(0)\n"
    # Eight mutants no filter skipped: three in a.py, three in b.py and two in c.py.
    init_sessions = {
        "scripts/a.py": [["core/One", 2, False], ["core/Two", 2, False], ["core/Three", 2, False]],
        "scripts/b.py": [["core/One", 2, False], ["core/Two", 2, False], ["core/Three", 2, False]],
        "scripts/c.py": [["core/One", 2, False], ["core/Two", 2, False], ["core/Three", 2, True]]}
    plan = {"init_sessions": init_sessions, "killed_output": SUITE_FAILED_RUNNER_OUTPUT}

    def steps_of(control):
        return [c["tool"] if c["tool"].startswith("cr-filter") or c["tool"] == "python"
                else c["arguments"][0] for c in calls(control)]

    def run_limited(repository, control, base, head, venv, sessions, *flags):
        (control / "calls.log").write_text("")
        json_file = control / "mutants.json"
        json_file.unlink(missing_ok=True)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv), workers_flag, "1", kept_flag,
                               str(sessions), "--survived-and-errored-mutants-json-file",
                               str(json_file), *flags)
        return completed, (json.loads(json_file.read_text()) if json_file.exists() else None)

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, head_files)
        venv, control = fake_venv(scratch_name, plan)
        sessions = Path(scratch_name) / "sessions"
        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         at_most_flag, "2")
        steps = steps_of(control)
        first_two = mutants_with_a_result_in_kept_sessions(sessions)
        ran = [c["arguments"] for c in calls(control) if c["tool"] == "python"]
        check("at most 2 mutants of three files: every file's session is made and filtered "
              "before any baseline, then only two files get a baseline and one mutant each, and "
              "every session is dumped",
              steps[:9] == ["init", "cr-filter-git", "cr-filter-pragma"] * 3
              and sorted(steps[9:]) == sorted(["dump"] + ["baseline", "dump", "python", "dump"] * 2)
              and " ".join(steps[9:]).count("baseline dump python dump") == 2
              and len(first_two) == 2 and len({path for path, *_ in first_two}) == 2,
              f"rc={completed.returncode} steps={steps} ran={first_two} err={completed.stderr}")
        check("the workers are given the job id of each chosen mutant, one for each of the two "
              "files, and no time after which no mutant starts",
              len(ran) == 2 and all(len(arguments[4]) == 32 and arguments[5] == "never"
                                    for arguments in ran), ran)
        check("the mutants left with no result are counted as not run in the SUMMARY line and "
              "the JSON file, and make the exit 1; RESUMED is not printed",
              completed.returncode == 1
              and "SUMMARY: 2 mutants on changed lines of 3 file(s): 2 killed, 0 survived, "
                  "0 errored, 6 not run" in completed.stdout
              and written is not None and written["mutants_not_run_count"] == 6
              and "RESUMED" not in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} json={written}")

        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         at_most_flag, "2")
        check("the same number again, with the sessions kept: the same mutants are chosen, they "
              "have a result, so no session is made and neither a baseline nor a mutant runs",
              steps_of(control) == ["dump"] * 3
              and mutants_with_a_result_in_kept_sessions(sessions) == first_two
              and written["mutants_not_run_count"] == 6,
              f"steps={steps_of(control)} out={completed.stdout} err={completed.stderr}")

        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         at_most_flag, "5")
        five = mutants_with_a_result_in_kept_sessions(sessions)
        asked_for = [job_id for c in calls(control) if c["tool"] == "python"
                     for job_id in c["arguments"][4].split(",")]
        check("a larger number runs other mutants, never one that has a result: 3 more are "
              "run, shared among the three files",
              completed.returncode == 1 and len(asked_for) == 3 and first_two < five
              and len(five) == 5
              and sorted(sum(1 for path, *_ in five if path == each)
                         for each in init_sessions) == [1, 2, 2]
              and written["mutants_not_run_count"] == 3,
              f"rc={completed.returncode} asked_for={asked_for} five={five} "
              f"err={completed.stderr}")

        future = repr(time.time() + 3600)
        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         stop_flag, future)
        ran = [c["arguments"] for c in calls(control) if c["tool"] == "python"]
        every = mutants_with_a_result_in_kept_sessions(sessions)
        check("with a time after which no mutant starts that has not come, and no number: every "
              "mutant with no result is run, the workers given that time, and the exit is 0",
              completed.returncode == 0 and len(every) == 8 and five < every
              and ran and all(arguments[4:6] == ["all", future] for arguments in ran)
              and written["mutants_not_run_count"] == 0,
              f"rc={completed.returncode} ran={ran} every={every} err={completed.stderr}")
        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         stop_flag, future)
        check("a file whose every mutant has a result prints RESUMED, and gets no baseline",
              completed.returncode == 0 and completed.stdout.count("RESUMED  ") == 3
              and steps_of(control) == ["dump"] * 3,
              f"rc={completed.returncode} steps={steps_of(control)} out={completed.stdout}")

        # The sessions made anew have new job ids for the same mutants.
        for session in sessions.glob("*.sqlite"):
            session.unlink()
        completed, _ = run_limited(repository, control, base, head, venv, sessions,
                                   at_most_flag, "2")
        check("with the sessions made anew, which gives every mutant a new job id, the same "
              "head has the same two mutants chosen",
              mutants_with_a_result_in_kept_sessions(sessions) == first_two,
              (mutants_with_a_result_in_kept_sessions(sessions), first_two))

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, head_files)
        venv, control = fake_venv(scratch_name, plan)
        sessions = Path(scratch_name) / "sessions"
        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         stop_flag, repr(time.time() - 1))
        check("with a time after which no mutant starts that has come: every session is made, "
              "no baseline and no mutant runs, every mutant is counted as not run, the JSON "
              "file is written, and the exit is 1",
              completed.returncode == 1
              and steps_of(control) == ["init", "cr-filter-git", "cr-filter-pragma"] * 3
              + ["dump"] * 3
              and "0 killed, 0 survived, 0 errored, 8 not run" in completed.stdout
              and written is not None and written["mutants_not_run_count"] == 8,
              f"rc={completed.returncode} steps={steps_of(control)} out={completed.stdout} "
              f"err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, head_files)
        # No init_sessions: this fake's init writes a session that is no sqlite file.
        venv, control = fake_venv(scratch_name, {"dump": []})
        sessions = Path(scratch_name) / "sessions"
        completed, written = run_limited(repository, control, base, head, venv, sessions,
                                         at_most_flag, "2")
        check("a session that cannot be read, when mutants must be chosen: exit 2, saying which "
              "session and to delete it, no baseline run, and the worktree removed",
              completed.returncode == 2 and written is None
              and "cannot be read (DatabaseError: file is not a database), so the mutants to "
                  "run cannot be chosen" in completed.stderr
              and "Delete that session file" in completed.stderr
              and "baseline" not in steps_of(control) and len(worktrees_of(repository)) == 1,
              f"rc={completed.returncode} steps={steps_of(control)} err={completed.stderr}")


def run_mutants_run_at_most_case_with_real_cosmic_ray():
    venv = load_script_module().DEFAULT_COSMIC_RAY_VENV
    if not (venv / "bin" / "cosmic-ray").is_file():
        print(f"SKIP  [this machine cannot run it] at most so many mutants run with the real "
              f"cosmic-ray: no cosmic-ray venv at {venv}")
        return
    script = load_script_module()
    suite = ("import importlib.util, pathlib\n"
             "spec = importlib.util.spec_from_file_location('thing', "
             "pathlib.Path(__file__).with_name('{name}.py'))\n"
             "module = importlib.util.module_from_spec(spec)\n"
             "spec.loader.exec_module(module)\n"
             "assert module.double(3) == 6\nprint('all cases passed')\n")
    head_files = {"scripts/thing.py": "def double(x):\n    return x + x\n",
                  "scripts/thing-test.py": suite.format(name="thing"),
                  "scripts/other.py": "def double(x):\n    return x * 2\n",
                  "scripts/other-test.py": suite.format(name="other")}
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, head_files)
        control = Path(scratch_name) / "control"
        control.mkdir()
        sessions = Path(scratch_name) / "sessions"
        judged = []
        summaries = []
        # One worker: this case's suites take the machine lock, which a second worker's would be
        # refused.
        for flags in (["2"], ["2"], ["3"], None):
            limit = [] if flags is None else [
                script.MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG, *flags]
            completed = run_script(
                repository, control, "--head", head, "--base", base, "--cosmic-ray-venv",
                str(venv), "--parallel-mutant-workers", "1",
                script.COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG, str(sessions), *limit)
            judged.append(mutants_with_a_result_in_kept_sessions(sessions))
            summaries.append([line for line in completed.stdout.splitlines()
                              if line.startswith("SUMMARY:")] or completed.stderr)
        check("with the real cosmic-ray: at most 2 mutants judges one mutant of each of the two "
              "files; the same number again judges no other; 3 judges one more; and a run with "
              "no number judges the rest, none twice",
              len(judged[0]) == 2 and len({path for path, *_ in judged[0]}) == 2
              and judged[1] == judged[0] and len(judged[2]) == 3 and judged[0] < judged[2]
              and judged[2] < judged[3] and " 0 not run" in summaries[3][0]
              and " 0 errored" in summaries[3][0], (judged, summaries))


def in_test_sandboxes_through_a_fake_bwrap(scratch_name):
    """run_script's keyword arguments that make the suites run in nc-test-sandboxes, as on a
    Linux machine with bwrap, through a fake bwrap on PATH; the variable that marks a run
    already inside the sandbox is dropped, since this file itself runs inside the suite
    runner's."""
    fake_bin = Path(scratch_name) / "bin"
    fake_bin.mkdir()
    (fake_bin / "bwrap").write_text("#!/bin/sh\nexit 0\n")
    (fake_bin / "bwrap").chmod(0o755)
    return {"path_override": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "dropped_variables": (load_test_suite_runner().SIGNAL_SANDBOX_INSIDE_VARIABLE,)}


def run_parallel_mutants_and_kept_sessions_cases():
    flag = load_script_module().PARALLEL_MUTANT_WORKERS_FLAG
    kept_flag = load_script_module().COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG
    for case_name, flags, wanted in [
        ("--parallel-mutant-workers 0", [flag, "0", "--cosmic-ray-venv", "/nowhere"],
         "--parallel-mutant-workers needs a count of 1 or more"),
    ]:
        completed = subprocess.run([sys.executable, str(SCRIPT), "--full-mutation-pass",
                                    "--head", "a", "--base", "b", *flags],
                                   capture_output=True, text=True, check=False)
        check(f"{case_name} exits 2 and says why",
              completed.returncode == 2 and wanted in completed.stderr, completed.stderr)
    if not sys.platform.startswith("linux"):
        print("SKIP  [this machine cannot run it] the parallel mutant workers' and kept "
              "sessions' cases: parallel workers need nc-test-sandboxes, which bwrap gives only "
              "on Linux, and the nightly pass that keeps sessions runs on ned-box only")
        return
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "b"),
             result("killed")]]})
        sessions = Path(scratch_name) / "sessions"
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv), flag, "3", kept_flag,
                               str(sessions), **in_test_sandboxes_through_a_fake_bwrap(
                                   scratch_name))
        recorded = calls(control)
        steps = [c["tool"] if c["tool"].startswith("cr-filter") or c["tool"] == "python"
                 else c["arguments"][0] for c in recorded]
        parallel = [c for c in recorded if c["tool"] == "python"]
        workers = json.loads((control / "parallel-workers.json").read_text()) \
            if (control / "parallel-workers.json").exists() else []
        kept = sorted(path.name for path in sessions.iterdir()) if sessions.is_dir() else []
        check("with --parallel-mutant-workers 3: exit 0, and the venv's python runs this "
              "script's parallel workers in place of cosmic-ray exec",
              completed.returncode == 0
              and steps == ["baseline", "dump", "init", "cr-filter-git", "cr-filter-pragma",
                            "python", "dump"]
              and parallel and parallel[0]["arguments"][:2] == [
                  str(SCRIPT.resolve()),
                  load_script_module().COSMIC_RAY_SESSION_PENDING_MUTANTS_RUN_BY_PARALLEL_WORKERS_FLAG],
              f"rc={completed.returncode} steps={steps} err={completed.stderr}")
        check("each of the 3 workers has a worktree of its own at the head, the first the one "
              "cosmic-ray's own steps run in",
              len(workers) == 3 and len({worktree for worktree, _ in workers}) == 3
              and all(commit == head for _, commit in workers)
              and workers[0][0] == recorded[0]["cwd"], (workers, recorded[:1]))
        check("every worktree is removed after the run",
              len(worktrees_of(repository)) == 1
              and not any(Path(worktree).exists() for worktree, _ in workers),
              worktrees_of(repository))
        check("the session is kept in the directory given, filtered, with no partial file left",
              len(kept) == 1 and kept[0].endswith(".sqlite")
              and parallel[0]["arguments"][3] == str(sessions.resolve() / kept[0]), kept)
        (control / "calls.log").write_text("")
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv), kept_flag, str(sessions))
        steps = [c["tool"] if c["tool"].startswith("cr-filter") else c["arguments"][0]
                 for c in calls(control)]
        check("a second run finds the kept session, says RESUMED, and runs cosmic-ray exec on "
              "it without init or the filters",
              completed.returncode == 0
              and "RESUMED  scripts/thing.py: its cosmic-ray session" in completed.stdout
              and steps == ["baseline", "dump", "exec", "dump"]
              and calls(control)[2]["arguments"][2] == str(sessions.resolve() / kept[0]),
              f"rc={completed.returncode} steps={steps} out={completed.stdout}")
        for pending, wanted_steps, wanted_out in [
                (0, ["dump"], "so neither its baseline nor any mutant runs"),
                (1, ["baseline", "dump", "exec", "dump"], "so only its mutants with no result run")]:
            kept_session = sessions / kept[0]
            kept_session.unlink()
            connection = sqlite3.connect(kept_session)
            connection.executescript(
                "CREATE TABLE work_items (job_id TEXT PRIMARY KEY);"
                "CREATE TABLE work_results (job_id TEXT PRIMARY KEY);"
                "INSERT INTO work_items VALUES ('done'); INSERT INTO work_results VALUES ('done');"
                + ("INSERT INTO work_items VALUES ('waiting');" if pending else ""))
            connection.commit()
            connection.close()
            (control / "calls.log").write_text("")
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv), kept_flag, str(sessions))
            steps = [c["tool"] if c["tool"].startswith("cr-filter") else c["arguments"][0]
                     for c in calls(control)]
            check(f"a kept session with {pending} mutant(s) with no result: "
                  f"{'no baseline and nothing run, only its dump' if not pending else 'the baseline and exec run'}",
                  completed.returncode == 0 and steps == wanted_steps
                  and wanted_out in completed.stdout,
                  f"rc={completed.returncode} steps={steps} out={completed.stdout} "
                  f"err={completed.stderr}")
    script = load_script_module()
    kept_path = \
        script.cosmic_ray_session_kept_to_resume_path_for_one_file_head_base_and_quick_or_full_mutation_pass
    full = kept_path("/sessions", "h", "b", "scripts/thing.py", False)
    quick = kept_path("/sessions", "h", "b", "scripts/thing.py", True)
    earlier_name = script.scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(
        "h", "b", "scripts/thing.py") + ".sqlite"
    check("the quick and the full pass keep a file's session under different names, the full "
          "pass's the name earlier runs kept it under",
          full != quick and full.name == earlier_name, (full, quick))
    for case_name, plan, flags, setup, wanted in [
        ("a parallel worker run that fails", {"parallel_exit": 2}, [flag, "2"], None,
         "the 2 parallel mutant workers for scripts/thing.py failed (exit 2): a parallel "
         "worker failed"),
        ("a venv with no python", {}, [flag, "2"], "remove python", "bin/python is not there"),
        ("a sessions directory that is a file", {}, [kept_flag, "{scratch}/a-file"],
         "make a-file", "the cosmic-ray session of scripts/thing.py could not be kept at"),
        ("a kept session that cannot be put in place",
         {"init_makes_kept_session_a_directory": True}, [kept_flag, "{scratch}/sessions"], None,
         "the cosmic-ray session of scripts/thing.py could not be kept at"),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, dict(plan, dump=[]))
            if setup == "remove python":
                (venv / "bin" / "python").unlink()
            if setup == "make a-file":
                (Path(scratch_name) / "a-file").write_text("")
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv),
                                   *[each.format(scratch=scratch_name) for each in flags],
                                   **in_test_sandboxes_through_a_fake_bwrap(scratch_name))
            check(f"{case_name}: exit 2, standard error says why, and the worktrees are removed",
                  completed.returncode == 2 and wanted in completed.stderr
                  and len(worktrees_of(repository)) == 1,
                  f"rc={completed.returncode} err={completed.stderr} "
                  f"worktrees={worktrees_of(repository)}")
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": []})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv), flag, "2")
        check("more than one parallel worker where suites take the machine lock: exit 2 before "
              "any worktree or cosmic-ray run, saying why",
              completed.returncode == 2
              and "every worker but one would be refused it" in completed.stderr
              and len(worktrees_of(repository)) == 1 and calls(control) == [],
              f"rc={completed.returncode} err={completed.stderr}")


def run_hunk_shared_context_line_counts_and_replaced_lines_cases():
    survivors = load_script_module()

    def lines_of(letters):
        # Built at run time, so equal lines are not the same object, as a diff's lines are not.
        return [f"{letter} line" for letter in letters]

    # (old, new, lines shared at the start and at the end, the letters of the replaced lines).
    # The first case comes first because a mutant that negates the end loop's condition
    # returns at once on it but loops forever on most other cases.
    cases = [
        ("ac", "bc", (0, 1), "a"),
        ("", "", (0, 0), ""),
        ("a", "b", (0, 0), "a"),
        ("a", "ba", (0, 1), ""),
        ("aa", "abaa", (1, 1), ""),
        ("a", "a", (1, 0), ""),
        ("aaa", "aaba", (2, 1), ""),
        ("aa", "ba", (0, 1), "a"),
        ("aaba", "ba", (0, 2), "aa"),
        ("ab", "bb", (0, 1), "a"),
        ("ab", "b", (0, 1), "a"),
        ("a", "bab", (0, 0), "a"),
        ("aa", "baba", (0, 1), "a"),
        ("a", "", (0, 0), "a"),
        # Past 256, where CPython stops sharing one object for each small int.
        ("a" * 300 + "b", "a" * 300, (300, 0), "b"),
        ("aa" + "b" * 300, "a" + "b" * 300, (1, 300), "a"),
    ]
    for old_letters, new_letters, counts, replaced_letters in cases:
        old, new = lines_of(old_letters), lines_of(new_letters)
        got = (survivors.hunk_shared_context_line_counts(old, new),
               survivors.hunk_replaced_lines(old, new))
        if got != (counts, lines_of(replaced_letters)):
            check(f"a hunk's shared context line counts and replaced lines, old "
                  f"{old_letters[:12]!r} ({len(old)} lines), new {new_letters[:12]!r} "
                  f"({len(new)} lines)", False,
                  f"want {(counts, replaced_letters)} got {got}")
            # A mutant of these functions can loop forever in a later case.
            sys.exit(1)
    check("a hunk's shared context line counts and replaced lines are right for each case: "
          "lines shared at the start, at the end, overlapping both, none, and over 256",
          True)


def run_recorded_mutant_lines_on_main_search_cases():
    survivors = load_script_module()
    # Each file is on origin/main without a last newline, so its last line ends the file.
    # Hunk "dup" appears twice in each, so no mutant applies and the search for each hunk's
    # replaced lines decides; hunk "b" appears once, so neither is gone.
    files = {
        "replaced-lines-are-the-whole-file.py": "dup\ndup",
        "replaced-line-at-an-odd-place-and-the-end.py": "dup\ndup\nx\nb",
        "replaced-line-at-place-one.py": "dup\nb\ndup",
        "two-replaced-lines-at-the-end.py": "dup\ndup\nx\nb1\nb2",
    }
    replaced_lines = {
        "replaced-lines-are-the-whole-file.py": ["dup", "dup"],
        "replaced-line-at-an-odd-place-and-the-end.py": ["b"],
        "replaced-line-at-place-one.py": ["b"],
        "two-replaced-lines-at-the-end.py": ["b1", "b2"],
    }
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, _, head = scratch_repository(scratch_name, files)
        git(repository, "update-ref", "refs/remotes/origin/main", head)
        for path, replaced in replaced_lines.items():
            # Line 100 is past each file's end, so neither hunk is found at its own line.
            hunks = [(100, replaced, ["changed"]), (100, ["dup"], ["changed"])]
            on_main = survivors.recorded_mutant_lines_on_main(repository, path, hunks, None)
            check(f"a recorded mutant whose replaced lines origin/main has once and twice is not "
                  f"gone, and whether it applies cannot be told: {path}",
                  on_main is None, on_main)


def run_cases():
    run_hunk_shared_context_line_counts_and_replaced_lines_cases()
    run_recorded_mutant_lines_on_main_search_cases()
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
              "worktree it runs in, of the sibling suite only, recording nothing and stopping at "
              "the first failing suite, with the given interpreter, recordings and lock",
              test_command_words[:4]
              == cosmic_ray_timeout_line_and_test_command_words_for_limit(45)[1]
              and Path(test_command_words[4]).parent == temporary_directory.resolve()
              and Path(test_command_words[4]).name.startswith(
                  load_script_module().TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX)
              and test_command_words[5:] == [
                  sys.executable, str(SCRIPT.resolve().with_name("run-all-test-suites.py")),
                  "--checkout", ".", "--python", "/usr/bin/python3",
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
               "scripts/run-all-test-suites.py: not run to the end — admission failed: gone\n")]],
         1, "0 killed, 0 survived, 1 errored"),
        ("the ERRORED line for a run not run to the end quotes the runner's line",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "PASS scripts/thing-test.py (0.4s)\n"
               "scripts/run-all-test-suites.py: not run to the end — admission failed: gone\n")]],
         1, "its output says: scripts/run-all-test-suites.py: not run to the end — admission failed: "
            "gone)"),
        ("a killed mutant the test command stopped at the limit on one run of the suites is "
         "ERRORED with the timeout, not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               f"{load_script_module().TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX}: it ran past "
               f"the limit of 45 s on one run of the suites\n"
               "FAIL scripts/thing-test.py exit 1 (0.4s)\n"
               "scripts/run-all-test-suites.py: not run to the end — stopped by SIGTERM.\n")]],
         1, "ERRORED   scripts/thing.py:2 core/NumberReplacer (timeout: the suites ran past "
            "the limit of"),
        ("a killed mutant the suite runner stopped at its run time limit is ERRORED with the "
         "timeout, not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "PASS scripts/other-test.py (0.4s)\n"
               f"{load_test_suite_runner().RUN_STOPPED_AT_RUN_TIME_LIMIT_NOT_COUNTING_ADMISSION_WAITS_LINE_PREFIX}"
               " of 45 s, not counting the time in which a suite waited for admission\n")]],
         1, "ERRORED   scripts/thing.py:2 core/NumberReplacer (timeout: the suites ran past "
            "the limit of"),
        ("a killed mutant whose failing suite was killed by a signal Python has no name for is "
         "killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(runner_output_with_a_suite_failed_with_exit_code(
               "scripts/thing-test.py", -40))]],
         0, "1 killed, 0 survived, 0 errored"),
        ("a killed mutant whose suite had a process killed at its memory ceiling, as a "
         "mutant that allocates without end does, is killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(runner_output_with_a_suite_failed_with_exit_code(
               "scripts/thing-test.py", -9,
               {"processes killed": 1, "ceiling": 4 * 10**9}))]],
         0, "1 killed, 0 survived, 0 errored"),
        ("a killed mutant whose every suite passed but whose records could not be written "
         "is ERRORED, not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "PASS scripts/thing-test.py (0.4s)\n"
               "scripts/run-all-test-suites.py: the run's case times, suite resources, JUnit XML or "
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
          and "scripts/run-all-test-suites.py: not run — another run holds" in refused.stdout
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
                  "so this mutant was not judged; its output says: scripts/run-all-test-suites.py: not "
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
        check("the suite runner, given the limit by the test command, stops itself at that "
              "limit and says so, so the test command's backstop never fires",
              ran.get("exit") == 2
              and load_test_suite_runner(
              ).RUN_STOPPED_AT_RUN_TIME_LIMIT_NOT_COUNTING_ADMISSION_WAITS_LINE_PREFIX
              in ran.get("stdout", "")
              and load_script_module().TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX
              not in ran.get("stdout", ""), ran)
        check("a suite running when the test command stops the suite runner has ended, before "
              "cosmic-ray's own limit",
              suite_pid is not None and not suite_still_running
              and seconds < 15 + EXTRA_SECONDS,
              (suite_pid, suite_still_running, seconds))

    # ------------------------------------------------------------------
    # The test command's backstop stops a runner that outlives the
    # admission ceiling and its own run time limit together.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        script = load_script_module()
        backstops = []

        def two_second_backstop(seconds, runner):
            backstops.append((seconds, runner.TEST_SUITE_ADMISSION_WAIT_CEILING_SECONDS))
            return 2

        class OutputCountingFlushes(io.StringIO):
            flushes = 0

            def flush(self):
                self.flushes += 1
                super().flush()

        script.test_suite_runner_backstop_seconds = two_second_backstop
        started = time.monotonic()
        # Flushed before the SIGTERM, so the line comes before what the runner prints as it stops.
        with contextlib.redirect_stdout(OutputCountingFlushes()) as printed:
            exit_code = script.run_test_suite_runner_with_its_stderr_on_stdout_stopped_before_cosmic_ray_limit(
                1.0, scratch_name, [sys.executable, "-c", "import time; time.sleep(60)"])
        seconds = time.monotonic() - started
        check("a runner still running at the test command's backstop is sent SIGTERM, and the "
              "test command says it stopped it, with the backstop's seconds",
              exit_code == -signal.SIGTERM and seconds < 30
              and backstops == [(1.0, ADMISSION_WAIT_CEILING_SECONDS)]
              and printed.getvalue().startswith(
                  f"{script.TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX}: it ran past 2 s")
              and printed.flushes >= 1,
              (exit_code, seconds, backstops, printed.getvalue(), printed.flushes))

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
    placeholder_command = load_script_module().build_argv_with_cosmic_ray_venv_flags_replaced_by_placeholder
    for case_name, argv, expected in [
            ("no venv flag given", ["s.py", "--head", "h"], ["s.py", "--head", "h"]),
            ("the flag and its value as two words", ["s.py", "--cosmic-ray-venv", "/v", "--head", "h"],
             ["s.py", "--head", "h"]),
            ("the flag with =", ["s.py", "--cosmic-ray-venv=/v", "--head", "h"], ["s.py", "--head", "h"]),
            ("the shortest abbreviation argparse accepts, given twice",
             ["s.py", "--cosmic-ray-v", "/v", "--cosmic-ray-ve=/w"], ["s.py"]),
            ("--checkout is kept, though it shares --c with the flag",
             ["s.py", "--checkout", "/c"], ["s.py", "--checkout", "/c"]),
            ("an empty option value is kept, with the option after it",
             ["s.py", "--base", "", "--checkout", "/c"], ["s.py", "--base", "", "--checkout", "/c"]),
            ("a - option value is kept, with the option after it",
             ["s.py", "--base", "-", "--checkout", "/c"], ["s.py", "--base", "-", "--checkout", "/c"]),
            ("--cosmic-ray-sessions-directory-kept-to-resume is kept",
             ["s.py", "--cosmic-ray-sessions-directory-kept-to-resume", "/s"],
             ["s.py", "--cosmic-ray-sessions-directory-kept-to-resume", "/s"])]:
        got = placeholder_command(argv)
        check(f"rerun command with the venv placeholder, {case_name}: every venv flag taken out "
              "and one placeholder flag put at the end",
              got == expected + ["--cosmic-ray-venv", "<that venv>"], got)

    # The length the function matches from must be the shortest abbreviation parse_arguments
    # accepts, so a parser option added later that shares more of the flag's name fails here.
    script = load_script_module()
    shortest = "--cosmic-ray-venv"[:script.SHORTEST_COSMIC_RAY_VENV_FLAG_ABBREVIATION_LENGTH]
    for abbreviation, accepted in ((shortest, True), (shortest[:-1], False)):
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                parsed = script.parse_arguments(
                    ["--quick-mutation-pass", "--head", "h", "--base", "b", abbreviation, "/v"])
            got = parsed.cosmic_ray_venv == "/v"
        except SystemExit:
            got = False
        check(f"parse_arguments {'accepts' if accepted else 'refuses'} {abbreviation!r}, so the "
              "rerun command's flag matching starts at the shortest abbreviation it accepts",
              got == accepted, f"accepted={got}")

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        _, control = fake_venv(scratch_name, {})
        empty_venv = Path(scratch_name) / "empty-venv"
        (empty_venv / "bin").mkdir(parents=True)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(empty_venv))
        check("cosmic-ray missing from the given venv: exit 2, saying how to install it",
              completed.returncode == 2
              and f"python3 -m venv {empty_venv}\n" in completed.stderr
              and f"{empty_venv}/bin/pip install cosmic-ray==" in completed.stderr
              and str(empty_venv / "bin") in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        rerun = completed.stderr.partition("Then run again:\n  python3 ")[2].split("\n")[0]
        check("cosmic-ray missing: the message names the machine and the command to run again",
              f"on {socket.gethostname()}, the machine this ran on" in completed.stderr
              and "--cosmic-ray-venv" in rerun and str(empty_venv) in rerun and head in rerun,
              f"err={completed.stderr}")
        before_install, _, _ = completed.stderr.partition("python3 -m venv ")
        existing_venv_command = before_install.partition(
            "replaced by the venv's path:\n  python3 ")[2].split("\n")[0]
        check("cosmic-ray missing: before the install steps, the message prints the command to "
              "run with a venv that already holds cosmic-ray, its --cosmic-ray-venv given once, "
              "as the placeholder to fill in",
              "from another machine, run them over ssh to it" in before_install
              and existing_venv_command.endswith(" --cosmic-ray-venv '<that venv>'")
              and existing_venv_command.count("--cosmic-ray-venv") == 1
              and str(empty_venv) not in existing_venv_command and head in existing_venv_command,
              f"err={completed.stderr}")
        home = Path(scratch_name) / "home"
        home.mkdir()
        default_venv = home / ".local" / "share" / "nedschorus" / "cosmic-ray-venv"
        completed = run_script(repository, control, "--head", head, "--base", base,
                               extra_environment={"HOME": str(home)})
        check("no venv given, and none in the home directory: exit 2, saying how to build the "
              "lasting one there, not in /tmp/cosmic-ray-venv",
              completed.returncode == 2
              and f"python3 -m venv {default_venv}\n" in completed.stderr
              and f"{default_venv}/bin/pip install cosmic-ray==" in completed.stderr
              and "/tmp/cosmic-ray-venv" not in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("no worktree is made when cosmic-ray is missing",
              len(worktrees_of(repository)) == 1, worktrees_of(repository))
        default_venv.parent.mkdir(parents=True)
        (Path(scratch_name) / "venv").rename(default_venv)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               extra_environment={"HOME": str(home)})
        check("no venv given: cosmic-ray is run from the venv in the home directory",
              completed.returncode == 0 and calls(control),
              f"rc={completed.returncode} err={completed.stderr}")

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

    # A cosmic-ray that cannot start writes no baseline session: it is reported as such, with
    # how to rebuild its venv, not as failing suites.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"baseline_cannot_import_cosmic_ray": True})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a cosmic-ray that cannot import its packages: exit 2, naming it, its error and "
              "how to rebuild its venv, not failing suites, and nothing dumped",
              completed.returncode == 2
              and f"{venv.resolve() / 'bin' / 'cosmic-ray'} exited 1 without making its "
              f"baseline session, so no suite ran" in completed.stderr
              and "cannot import name 'asdict' from 'attrs'" in completed.stderr
              and f"  rm -rf {venv.resolve()}\n" in completed.stderr
              and f"  {venv.resolve()}/bin/pip install cosmic-ray==" in completed.stderr
              and "fail on the unmutated head" not in completed.stderr
              and [c["arguments"][0] for c in calls(control)] == ["baseline"]
              and len(worktrees_of(repository)) == 1,
              f"rc={completed.returncode} err={completed.stderr} calls={calls(control)}")
        rebuild_steps = completed.stderr.partition(
            "ModuleNotFoundError, the venv holding cosmic-ray is broken")[2]
        check("a cosmic-ray that cannot import its packages: running again is a step of the "
              "venv rebuild, and any other error is to be fixed before running again",
              "rebuild it and run again:\n  rm -rf " in rebuild_steps
              and f"\n  python3 {SCRIPT}" in rebuild_steps.partition(
                  "\nIf cosmic-ray's last line names any other")[0]
              and "If cosmic-ray's last line names any other error, running again unchanged fails "
              "the same way: fix that error, then run only the last of the four commands above."
              in rebuild_steps,
              f"err={completed.stderr}")

    # ------------------------------------------------------------------
    # A baseline that ran out of time is reported as a timeout, not as
    # failing suites, and exits 2; a baseline whose suite runner, run to
    # its end, names a suite failing by its own exit exits 3 naming it;
    # any other killed baseline exits 2 and still says the suites fail.
    # ------------------------------------------------------------------
    baseline_item = {"job_id": "baseline", "mutations": []}
    runner = load_test_suite_runner()
    survivors_module = load_script_module()
    suite_fails_line = (f"{survivors_module.SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX}"
                        f"scripts/thing-test.py\n")
    for case_name, plan, flags, wanted_exit, wanted, unwanted in [
        ("a baseline killed with cosmic-ray's timeout output exits 2, says the suites ran out "
         "of time, gives the limit and says to raise --mutant-timeout-seconds",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output("timeout")]]},
         ("--mutant-timeout-seconds", "45"), survivors_module.EXIT_COULD_NOT_RUN,
         ["ran out of time on the unmutated head", "the limit of 45 s on one run of them",
          "Run this again with --mutant-timeout-seconds larger than 45."], ["fail"]),
        ("a baseline killed with the suite runner's TIMEOUT line exits 2 naming the suite and "
         "its own limit",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             runner_output_with_suites_timed_out([("scripts/thing-test.py", 1800)]))]]},
         (), survivors_module.EXIT_COULD_NOT_RUN,
         ["on the unmutated head, scripts/thing-test.py ran past its own limit of 1800 s",
          "a larger --mutant-timeout-seconds does not raise it",
          "--only-suites-named scripts/thing-test.py\n"], ["fail"]),
        ("a baseline the suite runner stopped at its run time limit exits 2, says the suites "
         "ran out of time with that limit, admission waits not counted",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             f"{load_test_suite_runner().RUN_STOPPED_AT_RUN_TIME_LIMIT_NOT_COUNTING_ADMISSION_WAITS_LINE_PREFIX}"
             " of 45 s, not counting the time in which a suite waited for admission\n")]]},
         ("--mutant-timeout-seconds", "45"), survivors_module.EXIT_COULD_NOT_RUN,
         ["ran out of time on the unmutated head",
          "the limit of 45 s on one run of them passed, admission waits not counted",
          "Run this again with --mutant-timeout-seconds larger than 45."], ["fail"]),
        ("a baseline whose suite got no test slot exits 2, quotes the runner's line, and says "
         "to run again when the machine is quieter, not to raise --mutant-timeout-seconds",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             f"{load_test_suite_runner().TEST_SUITE_ADMISSION_WAIT_CEILING_PASSED_LINE_PREFIX}: "
             "scripts/thing-test.py waited 28800 s\n")]]},
         (), survivors_module.EXIT_COULD_NOT_RUN,
         ["got no test slot", "a larger --mutant-timeout-seconds does not help",
          ": scripts/thing-test.py waited 28800 s\n",
          "Run this again once the machine is quieter."],
         ["fail", "ran out of time", "larger than"]),
        ("a baseline killed with the suite runner's FAIL line for a suite's own exit exits 3 "
         "and names that suite on a line of its own",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             runner_output_with_a_suite_failed_with_exit_code("scripts/thing-test.py", 1))]]},
         (), survivors_module.EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD,
         ["fails on the unmutated head", suite_fails_line, "give that commit as --head"],
         ["ran out of time", "ran past its own limit"]),
        ("a baseline killed with a suite's FAIL line from a suite runner not run to the end "
         "exits 2, naming no suite as failing",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             runner_output_with_a_suite_failed_with_exit_code("scripts/thing-test.py", 1)
             + f"{runner.NOT_RUN_TO_THE_END_LINE_PREFIX}: stopped\n")]]},
         (), survivors_module.EXIT_COULD_NOT_RUN, ["fail on the unmutated head"],
         ["suite fails on unmutated head", "ran out of time"]),
        ("a baseline killed with an nc-test-sandbox that did not start exits 2, naming no "
         "suite as failing",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             runner_output_with_test_sandbox_not_started("scripts/thing-test.py"))]]},
         (), survivors_module.EXIT_COULD_NOT_RUN, ["fail on the unmutated head"],
         ["suite fails on unmutated head", "ran out of time"]),
        ("a baseline killed with output that names no failing suite exits 2 and still says "
         "the suites fail",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             "Traceback (most recent call last): the suite runner crashed\n")]]},
         (), survivors_module.EXIT_COULD_NOT_RUN, ["fail on the unmutated head"],
         ["suite fails on unmutated head", "ran out of time", "ran past its own limit"]),
        ("a failing baseline whose result cannot be dumped exits 2 and still says the suites "
         "fail",
         {"baseline_exit": 1, "baseline_dump_exit": 4},
         (), survivors_module.EXIT_COULD_NOT_RUN, ["fail on the unmutated head"],
         ["suite fails on unmutated head", "ran out of time", "ran past its own limit"]),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, plan)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv), *flags)
            check(case_name,
                  completed.returncode == wanted_exit
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
         "baseline fail and the script exit 3",
         "import sys\nsys.exit(1)\n", 3, 1, "FAIL scripts/thing-test.py exit 1"),
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
                    survivors_module.FULL_MUTATION_PASS_COMMAND_LINE_FLAG,
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

    run_recorded_mutant_killed_check_cases()
    run_test_suite_runner_log_directories_cases()
    run_log_directories_parent_retention_and_stop_signal_cases()
    run_recorded_mutant_could_not_be_judged_log_directory_kept_case()
    run_parallel_mutants_and_kept_sessions_cases()
    run_parallel_mutant_workers_cases_with_fake_cosmic_ray_package()
    run_parallel_mutant_workers_case_with_real_cosmic_ray()
    run_mutants_run_at_most_and_no_mutant_started_after_unix_time_cases()
    run_mutants_run_at_most_case_with_real_cosmic_ray()

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
