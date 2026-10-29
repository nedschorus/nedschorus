#!/usr/bin/env python3
"""Tests for scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py.

Run: python3 scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open-test.py
Prints one line per case and exits non-zero if any case fails.

No case runs cosmic-ray or the real mutation testing program. Each case builds an
origin repository and a clone of it, and passes --mutation-testing-program a fake
that records its arguments and, for each head it is given, writes the JSON file
and exits as the case's plan says.
"""

import fcntl
import importlib.util
import json
import os
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

SCRIPT = Path(__file__).with_name(
    "scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py")
PLAN_VARIABLE = "SCHEDULED_FULL_MUTATION_PASS_TEST_PLAN_FILE"


def load_script_module():
    spec = importlib.util.spec_from_file_location(
        "scheduled_full_mutation_pass_of_merged_pull_requests_and_survivor_tasks_open",
        str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


job = load_script_module()

FAKE_MUTATION_TESTING_PROGRAM = f'''#!/usr/bin/env python3
import json, os, pathlib, signal, sys, time
plan_file = pathlib.Path(os.environ["{PLAN_VARIABLE}"])
plan = json.loads(plan_file.read_text())
arguments = sys.argv[1:]
with (plan_file.parent / "calls.log").open("a") as log:
    log.write(json.dumps(arguments) + "\\n")
head = arguments[arguments.index("--head") + 1]
step = plan.get(head, {{}})
def stopped(number, frame):
    (plan_file.parent / "stopped-by-sigterm").write_text(head)
    sys.exit(143)
signal.signal(signal.SIGTERM, stopped)
time.sleep(step.get("sleep", 0))
if "json" in step:
    pathlib.Path(arguments[arguments.index("--survived-and-errored-mutants-json-file") + 1]
                 ).write_text(json.dumps(step["json"]))
print("SUMMARY: " + step.get("summary", "0 mutants"))
print(step.get("stderr", ""), file=sys.stderr)
sys.exit(step.get("exit", 0))
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repository, *arguments, author="tester"):
    # The author variables, which an agent-seat's environment sets, outrank user.name.
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        env={**os.environ, "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": "t@example.invalid",
             "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": "t@example.invalid"},
        capture_output=True, text=True, check=True).stdout.strip()


class Fixture:
    """An origin, a working repository that pushes to it, the clone the job tests, and its
    state, task lists, agent-seat checkouts, cosmic-ray venv and log-store."""

    def __init__(self, directory):
        self.root = Path(directory)
        self.origin = self.root / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)],
                       check=True)
        self.work = self.root / "work"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.work)], check=True,
                       capture_output=True)
        self.commit("README", "base\n")
        self.clone = self.root / "clone"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.clone)], check=True)
        self.state = self.root / "state"
        self.tasks = self.root / "tasks"
        self.agents = self.root / "agents"
        self.venv = self.root / "venv"
        (self.venv / "bin").mkdir(parents=True)
        (self.venv / "bin" / "cosmic-ray").write_text("")
        self.log_store = self.root / "log-store"
        self.program = self.root / "fake-mutation-testing.py"
        self.program.write_text(FAKE_MUTATION_TESTING_PROGRAM)
        self.plan_file = self.root / "plan.json"
        self.plan_file.write_text("{}")

    def commit(self, path, text, author="tester"):
        (self.work / path).parent.mkdir(parents=True, exist_ok=True)
        (self.work / path).write_text(text)
        git(self.work, "add", "-A", author=author)
        git(self.work, "commit", "-q", "-m", f"change {path}", author=author)
        git(self.work, "push", "-q", "origin", "HEAD:main")
        return git(self.work, "rev-parse", "HEAD")

    def seat(self, name, with_checkout=True):
        (self.tasks / f"nedschorus-{name}-tasks").mkdir(parents=True, exist_ok=True)
        if with_checkout:
            (self.agents / name).mkdir(parents=True, exist_ok=True)
        return self.tasks / f"nedschorus-{name}-tasks"

    def run(self, plan=None, *flags, timeout_seconds=None):
        if plan is not None:
            self.plan_file.write_text(json.dumps(plan))
        command = [sys.executable, str(SCRIPT), "--clone", str(self.clone),
                   "--log-store-root", str(self.log_store),
                   "--state-directory", str(self.state),
                   "--task-lists-directory", str(self.tasks),
                   "--agent-seats-directory", str(self.agents),
                   "--cosmic-ray-venv", str(self.venv),
                   "--mutation-testing-program", str(self.program)]
        if timeout_seconds is not None:
            command += ["--merge-timeout-seconds", str(timeout_seconds)]
        return subprocess.run([*command, *flags], capture_output=True, text=True, check=False,
                              env={**os.environ, PLAN_VARIABLE: str(self.plan_file)},
                              timeout=300)

    def state_json(self):
        return json.loads((self.state / job.STATE_FILE_NAME).read_text())

    def set_last(self, commit):
        state = self.state_json() if (self.state / job.STATE_FILE_NAME).exists() else {
            "tasks_opened": {}}
        state["last_tested_main_commit"] = commit
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / job.STATE_FILE_NAME).write_text(json.dumps(state))

    def records(self):
        directory = self.log_store / job.RECORDS_DIRECTORY_NAME
        return sorted(directory.iterdir()) if directory.exists() else []

    def calls(self):
        log = self.root / "calls.log"
        return [json.loads(line) for line in log.read_text().splitlines()] \
            if log.exists() else []


SURVIVOR_DIFF = "--- a/scripts/thing.py\n+++ b/scripts/thing.py\n-    return x + x\n+    return x * x\n"


def survivor(line=2, operator="core/ReplaceBinaryOperator_Add_Mul"):
    return {"module_path": "scripts/thing.py", "line": line, "operator": operator,
            "diff": SURVIVOR_DIFF, "reason": ""}


def verdict(survived=(), errored=(), no_suite=()):
    return {"head": "h", "merge_base": "b", "survived": list(survived),
            "errored": list(errored), "files_with_no_suite": list(no_suite)}


def task_files(list_directory):
    return sorted(path.name for path in list_directory.glob("*.json"))


def run_cases():
    # The first run writes the state file and tests nothing.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        main_commit = git(fixture.work, "rev-parse", "HEAD")
        completed = fixture.run()
        check("first run: exit 0", completed.returncode == 0,
              f"rc={completed.returncode} err={completed.stderr}")
        check("first run: the state file names origin/main and no task",
              fixture.state_json() == {"last_tested_main_commit": main_commit,
                                       "tasks_opened": {}}, fixture.state_json())
        check("first run: no merge is mutation-tested", fixture.calls() == [], fixture.calls())
        records = fixture.records()
        check("first run: the record says it is the first run, and the citation is printed",
              len(records) == 1 and "first run: no state file" in records[0].read_text()
              and f"nedlern@ned-box:{records[0]}" in completed.stdout,
              (records, completed.stdout))

    # Merges after the state's commit: each tested once, oldest first; a survivor's task on its
    # author's list, numbered after the list's highest id and high-water mark.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        first = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        second = fixture.commit("scripts/other.py", "VALUE = 1\n", author="beta")
        alpha_list = fixture.seat("alpha")
        (alpha_list / "3.json").write_text("{}")
        (alpha_list / ".highwatermark").write_text("5")
        (alpha_list / ".lock").write_text("")
        completed = fixture.run({
            first: {"json": verdict(
                survived=[survivor()],
                errored=[dict(survivor(1, "core/NumberReplacer"), reason="timeout: slow")],
                no_suite=["scripts/untested.py"]),
                "summary": "3 mutants", "exit": 1},
            second: {"json": verdict(), "summary": "0 mutants"}})
        calls = fixture.calls()
        check("merges: exit 0", completed.returncode == 0,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
        check("merges: each merge since the state's commit is tested once, oldest first, by "
              "the full mutation pass against its first parent, with the venv and a JSON file",
              [call[call.index("--head") + 1] for call in calls] == [first, second]
              and all(call[0] == "--full-mutation-pass" for call in calls)
              and calls[0][calls[0].index("--base") + 1] == start
              and calls[1][calls[1].index("--base") + 1] == first
              and all(call[call.index("--cosmic-ray-venv") + 1] == str(fixture.venv)
                      and "--survived-and-errored-mutants-json-file" in call for call in calls),
              calls)
        task = json.loads((alpha_list / "6.json").read_text()) \
            if (alpha_list / "6.json").exists() else {}
        check("merges: the survivor's task is on its author's list, numbered one past the "
              "higher of the highest id and the high-water mark, which is raised to it",
              task_files(alpha_list) == ["3.json", "6.json"]
              and (alpha_list / ".highwatermark").read_text() == "6" and task.get("id") == "6",
              (task_files(alpha_list), task))
        check("merges: the task is pending, names the line and asks for a test or the pragma",
              task.get("status") == "pending" and task.get("blocks") == []
              and task.get("blockedBy") == []
              and "scripts/thing.py:2" in task.get("subject", "")
              and "+    return x * x" in task.get("description", "")
              and "`# pragma: no mutate`" in task.get("description", "")
              and "You wrote the line." in task.get("description", ""), task)
        record = fixture.records()[0].read_text()
        check("merges: the record has each merge's SUMMARY, the task, the ERRORED mutant and the "
              "file with no suite",
              f"merge {first[:12]} change scripts/thing.py: SUMMARY: 3 mutants" in record
              and "SURVIVED scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Mul: task #6 "
                  "opened on alpha's task list" in record
              and "ERRORED scripts/thing.py:1 core/NumberReplacer (timeout: slow): no task"
                  in record
              and "NO SUITE scripts/untested.py" in record
              and f"merge {second[:12]} change scripts/other.py: SUMMARY: 0 mutants" in record
              and "merges tested: 2" in record, record)
        check("merges: the state names the last merge and the task given",
              fixture.state_json()["last_tested_main_commit"] == second
              and list(fixture.state_json()["tasks_opened"].values())
              == [{"agent_seat": "alpha", "task_id": 6}], fixture.state_json())

        # The same survivor found again gets no second task.
        third = fixture.commit("scripts/third.py", "VALUE = 3\n", author="alpha")
        completed = fixture.run({third: {"json": verdict(survived=[survivor()])}})
        check("a survivor already given a task gets no second one, and the record says which",
              completed.returncode == 0 and task_files(alpha_list) == ["3.json", "6.json"]
              and "already given task #6 on alpha's task list"
              in fixture.records()[-1].read_text(),
              (completed.returncode, task_files(alpha_list), completed.stderr))

    # An author with no checkout, or no task list, has the task put on merge-lane-2's list.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="retired")
        fixture.seat("retired", with_checkout=False)
        merge_lane = fixture.seat(job.SURVIVOR_TASK_AGENT_SEAT_WHEN_LINE_AUTHOR_IS_RETIRED_OR_UNKNOWN)
        completed = fixture.run({merge: {"json": verdict(survived=[survivor()])}})
        task = json.loads((merge_lane / "1.json").read_text()) \
            if (merge_lane / "1.json").exists() else {}
        check("a retired author's survivor goes on merge-lane-2's list, saying whose line it is",
              completed.returncode == 0
              and "Agent-seat retired wrote the line" in task.get("description", "")
              and "has no task list or no checkout on ned-box" in task.get("description", "")
              and task_files(fixture.tasks / "nedschorus-retired-tasks") == [],
              (completed.returncode, completed.stderr, task))

    # Failures: the run stops at the merge, records why, exits 4 and leaves the state there.
    for case_name, step, timeout_seconds, wanted in [
        ("the mutation testing program exits 2",
         {"exit": 2, "stderr": "mutation-testing: not run — cosmic-ray is missing"}, None,
         "exited 2 with no verdict: mutation-testing: not run — cosmic-ray is missing"),
        ("the mutation testing program runs past the limit",
         {"sleep": 30, "json": verdict()}, 1, "ran past the limit of 1 s and was stopped"),
        ("the mutation testing program writes no JSON file",
         {"exit": 0}, None, "but its JSON file"),
        ("the JSON file lacks a key",
         {"json": {"survived": []}}, None, "KeyError"),
    ]:
        with tempfile.TemporaryDirectory() as scratch:
            fixture = Fixture(scratch)
            start = git(fixture.work, "rev-parse", "HEAD")
            fixture.set_last(start)
            merge = fixture.commit("scripts/thing.py", "VALUE = 1\n")
            completed = fixture.run({merge: step}, timeout_seconds=timeout_seconds)
            record = fixture.records()[0].read_text() if fixture.records() else ""
            check(f"{case_name}: exit 4, the record and stderr say why, and the state is not "
                  f"advanced, so the next run tries the merge again",
                  completed.returncode == job.EXIT_STEP_FAILED
                  and wanted in record and wanted in completed.stderr
                  and "The next run tries this merge again" in record
                  and fixture.state_json()["last_tested_main_commit"] == start,
                  f"rc={completed.returncode} record={record} err={completed.stderr}")
            if timeout_seconds is not None:
                check(f"{case_name}: the program is stopped with SIGTERM, so it can remove its "
                      f"worktree", (fixture.root / "stopped-by-sigterm").exists())

    # No task list for the survivor at all: the merge is not recorded as tested.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="nobody")
        completed = fixture.run({merge: {"json": verdict(survived=[survivor()])}})
        check("a task that cannot be opened stops the run at that merge, exit 4, naming the list",
              completed.returncode == job.EXIT_STEP_FAILED
              and "no task could be opened on merge-lane-2's task list" in completed.stderr
              and "nedschorus-merge-lane-2-tasks does not exist" in completed.stderr
              and fixture.state_json()["last_tested_main_commit"] == start,
              f"rc={completed.returncode} err={completed.stderr}")

    # A state file that cannot be read, or names a commit not on origin/main.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.state.mkdir()
        (fixture.state / job.STATE_FILE_NAME).write_text("{not json")
        completed = fixture.run()
        check("a state file that is not JSON: exit 4, nothing tested, and the file is kept",
              completed.returncode == job.EXIT_STEP_FAILED
              and "cannot be read" in completed.stderr and fixture.calls() == []
              and (fixture.state / job.STATE_FILE_NAME).read_text() == "{not json",
              f"rc={completed.returncode} err={completed.stderr}")
        (fixture.state / job.STATE_FILE_NAME).write_text(
            json.dumps({"last_tested_main_commit": 7, "tasks_opened": {}}))
        completed = fixture.run()
        check("a state file whose commit is not a string: exit 4",
              completed.returncode == job.EXIT_STEP_FAILED
              and "a key holds the wrong type" in completed.stderr, completed.stderr)
        fixture.set_last("0" * 40)
        completed = fixture.run()
        check("a state file naming a commit not on origin/main: exit 4, saying how to fix it",
              completed.returncode == job.EXIT_STEP_FAILED
              and "is not an ancestor of origin/main" in completed.stderr
              and "Set last_tested_main_commit" in completed.stderr, completed.stderr)

    # No cosmic-ray venv, with merges to test.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        fixture.commit("scripts/thing.py", "VALUE = 1\n")
        (fixture.venv / "bin" / "cosmic-ray").unlink()
        completed = fixture.run()
        check("no cosmic-ray in the venv: exit 4, nothing tested, and the install command named",
              completed.returncode == job.EXIT_STEP_FAILED and fixture.calls() == []
              and f"bin/pip install cosmic-ray=={job.COSMIC_RAY_VERSION}" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")

    # A fetch that fails.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        git(fixture.clone, "remote", "set-url", "origin", str(fixture.root / "missing.git"))
        completed = fixture.run()
        check("a failed fetch: exit 4, and the record names the git command",
              completed.returncode == job.EXIT_STEP_FAILED
              and "git fetch --quiet origin main failed" in fixture.records()[0].read_text(),
              f"rc={completed.returncode} err={completed.stderr}")

    # Another run holds the lock.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.state.mkdir()
        with open(fixture.state / job.LOCK_FILE_NAME, "a") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            completed = fixture.run()
        check("another run holds the lock: exit 6, nothing done, no record",
              completed.returncode == job.EXIT_ANOTHER_RUN_HOLDS_THE_LOCK
              and "another run holds" in completed.stderr and fixture.records() == []
              and not (fixture.state / job.STATE_FILE_NAME).exists(),
              f"rc={completed.returncode} err={completed.stderr}")

    # A record that cannot be written is printed instead.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.log_store.mkdir()
        (fixture.log_store / job.RECORDS_DIRECTORY_NAME).write_text("a file, not a directory")
        completed = fixture.run()
        check("a record that cannot be written: exit 5, the record on stdout",
              completed.returncode == job.EXIT_RECORD_NOT_WRITTEN
              and "first run: no state file" in completed.stdout
              and "was not written to" in completed.stderr,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # A state file that cannot be opened at all.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        (fixture.state / job.STATE_FILE_NAME).mkdir(parents=True)
        completed = fixture.run()
        check("a state file that cannot be opened: exit 4, and the record names the error",
              completed.returncode == job.EXIT_STEP_FAILED
              and "FAILED: [Errno 21] Is a directory" in fixture.records()[0].read_text(),
              f"rc={completed.returncode} err={completed.stderr}")

    # A mutation testing program that ignores SIGTERM at the limit is killed.
    with tempfile.TemporaryDirectory() as scratch:
        program = Path(scratch) / "ignores-sigterm.py"
        program.write_text("import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                           "print('still going', flush=True)\ntime.sleep(60)\n")
        arguments = job.parse_arguments(["--mutation-testing-program", str(program),
                                         "--merge-timeout-seconds", "1"])
        cleanup_seconds = job.SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM
        job.SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM = 1
        try:
            exit_code, stdout, _ = job.run_mutation_testing(arguments, "a" * 40, "b" * 40,
                                                            Path(scratch) / "out.json")
        finally:
            job.SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM = cleanup_seconds
        check("a mutation testing program still running after SIGTERM and the time to clean up "
              "is killed, and reported as past the limit with its output kept",
              exit_code is None and "still going" in stdout, (exit_code, stdout))

    # agent_seat_task_list_new_pending_task_write: a task file Claude Code wrote under the chosen id at the same moment is kept.
    with tempfile.TemporaryDirectory() as scratch:
        list_directory = Path(scratch)
        (list_directory / ".highwatermark").write_text("not a number")
        (list_directory / "2.json").write_text("{}")
        real_link = job.os.link

        def link_racing_claude_code(source, target):
            if Path(target).name == "3.json" and not Path(target).exists():
                Path(target).write_text('{"id": "3", "by": "claude code"}')
            return real_link(source, target)

        job.os.link = link_racing_claude_code
        try:
            task_id = job.agent_seat_task_list_new_pending_task_write(list_directory, "subject", "description")
        finally:
            job.os.link = real_link
        check("agent_seat_task_list_new_pending_task_write: an id taken at the same moment is skipped, its file kept, a "
              "high-water mark that is not a number ignored, and no partial file left",
              task_id == 4 and json.loads((list_directory / "3.json").read_text())["by"]
              == "claude code"
              and json.loads((list_directory / "4.json").read_text())["subject"] == "subject"
              and (list_directory / ".highwatermark").read_text() == "4"
              and not list(list_directory.glob("*.partial")),
              (task_id, sorted(p.name for p in list_directory.iterdir())))


if __name__ == "__main__":
    run_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
