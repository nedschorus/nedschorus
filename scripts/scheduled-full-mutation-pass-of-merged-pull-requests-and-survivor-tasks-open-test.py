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
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

FLOCK_PROGRAM = Path("/usr/bin/flock")

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
import json, os, pathlib, signal, sqlite3, sys, time
plan_file = pathlib.Path(os.environ["{PLAN_VARIABLE}"])
plan = json.loads(plan_file.read_text())
arguments = sys.argv[1:]
with (plan_file.parent / "calls.log").open("a") as log:
    log.write(json.dumps(arguments) + "\\n")
head = arguments[arguments.index("--head") + 1]
rechecking = "--recorded-mutant-killed-check" in arguments
step = plan.get("recheck", {{}}) if rechecking else plan.get(head, {{}})
def stopped(number, frame):
    (plan_file.parent / "stopped-by-sigterm").write_text(head)
    sys.exit(143)
signal.signal(signal.SIGTERM, stopped)
if "judged_in_kept_session" in step:
    # As cosmic-ray 8.7.0 keeps a session: a row of work_results per mutant with a result.
    sessions = pathlib.Path(arguments[arguments.index(
        "--cosmic-ray-sessions-directory-kept-to-resume") + 1])
    sessions.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(sessions / "kept.sqlite")
    if step.get("kept_session_started_again"):
        connection.execute("DROP TABLE IF EXISTS work_results")
    connection.execute("CREATE TABLE IF NOT EXISTS work_results (job_id, worker_outcome)")
    connection.executemany("INSERT INTO work_results VALUES (?, ?)",
                           [(str(number), "NORMAL") for number in
                            range(step["judged_in_kept_session"])]
                           + [("skipped", "SKIPPED")])
    connection.commit()
    connection.close()
time.sleep(step.get("sleep", 0))
if rechecking:
    diff_files = arguments[arguments.index("--recorded-mutant-killed-check") + 1:
                           arguments.index("--head")]
    if not step.get("no_verdicts"):
        pathlib.Path(arguments[arguments.index(
            "--recorded-mutant-killed-check-verdicts-json-file-to-write") + 1]).write_text(
            json.dumps({{"head": head, "verdicts": {{
                name: {{"verdict": step.get("verdicts", {{}}).get(pathlib.Path(name).stem,
                                                               "survived"), "why": "fake"}}
                for name in diff_files}}}}))
    print(step.get("stdout", "RECORDED MUTANTS: fake"))
    print(step.get("stderr", ""), file=sys.stderr)
    sys.exit(step.get("exit", 1))
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

    def run(self, plan=None, *flags, timeout_seconds=None, output=None):
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
        streams = ({"capture_output": True} if output is None
                   else {"stdout": output, "stderr": subprocess.STDOUT})
        return subprocess.run([*command, *flags], **streams, text=True, check=False,
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
        # The surviving mutants' diffs are kept in a directory beside the records.
        return sorted(path for path in directory.iterdir() if path.is_file()) \
            if directory.exists() else []

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


def job_failure_tasks(fixture):
    directory = fixture.tasks / f"nedschorus-{job.JOB_FAILURE_TASK_AGENT_SEAT}-tasks"
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))]


def run_every_exit_but_0_6_7_9_opens_a_job_failure_task_cases():
    # Exit 7 opens none, because the job cannot tell a task a handoff deleted after it was
    # finished from a lost one.
    opened_for_exit = {}

    def ran(fixture, completed):
        opened_for_exit.setdefault(completed.returncode, []).append(job_failure_tasks(fixture))

    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        fixture.state.mkdir()
        (fixture.state / job.STATE_FILE_NAME).write_text("{not json")
        ran(fixture, fixture.run())

    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        fixture.run({merge: {"json": verdict(survived=[survivor()])}})
        ran(fixture, fixture.run({"recheck": {"no_verdicts": True, "exit": 2}}))

    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        fixture.log_store.mkdir()
        (fixture.log_store / job.RECORDS_DIRECTORY_NAME).write_text("a file, not a directory")
        completed = fixture.run()
        ran(fixture, completed)
        tasks = job_failure_tasks(fixture)
        check("a record that cannot be written opens one job failure task, giving the error and "
              "where the record went instead, and says so on standard error",
              completed.returncode == job.EXIT_RECORD_NOT_WRITTEN
              and [task["subject"] for task in tasks] == [job.RUN_RECORD_NOT_WRITTEN_TASK_SUBJECT]
              and "FileExistsError" in tasks[0]["description"]
              and job.JOB_LOG_FILE in tasks[0]["description"]
              and f"JOB FAILURE TASK: task #{tasks[0]['id']} on " in completed.stderr
              and f"\"{job.RUN_RECORD_NOT_WRITTEN_TASK_SUBJECT}\", opened." in completed.stderr,
              (completed.returncode, completed.stderr, tasks))
        task_file = (fixture.tasks / f"nedschorus-{job.JOB_FAILURE_TASK_AGENT_SEAT}-tasks"
                     / f"{tasks[0]['id']}.json")
        task_file.write_text(json.dumps({**tasks[0], "description": "an older night's"}))
        completed = fixture.run()
        check("a second run whose record cannot be written opens no second task, and rewrites "
              "the open task's description",
              completed.returncode == job.EXIT_RECORD_NOT_WRITTEN
              and len(job_failure_tasks(fixture)) == 1
              and "FileExistsError" in job_failure_tasks(fixture)[0]["description"]
              and "was already open, so this run rewrote its description with this run's error."
                  in completed.stderr,
              (completed.returncode, completed.stderr, job_failure_tasks(fixture)))

    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.log_store.mkdir()
        (fixture.log_store / job.RECORDS_DIRECTORY_NAME).write_text("a file, not a directory")
        completed = fixture.run()
        check("a record that cannot be written, whose task cannot be opened either, names both "
              "failures on standard error and still exits 5",
              completed.returncode == job.EXIT_RECORD_NOT_WRITTEN
              and "was not written to" in completed.stderr
              and "this run's record was not written could not be opened on "
                  f"{job.JOB_FAILURE_TASK_AGENT_SEAT}'s task list (FileNotFoundError"
                  in completed.stderr
              and f"the record's, in the line that begins \"{job.PROGRAM}: the record above "
                  "was not written\"" in completed.stderr
              and f"To check your fix sooner, run on ned-box: {job.RUN_BY_HAND}"
                  in completed.stderr
              and f"{job.PROGRAM}: the record above was not written" in completed.stderr,
              (completed.returncode, completed.stderr))
        one_file = fixture.root / "job.log"
        with one_file.open("w") as log:
            fixture.run(output=log)
        log_text = one_file.read_text()
        record_at = log_text.find("wall-clock seconds:")
        pointer_at = log_text.find(f"{job.PROGRAM}: the record above was not written")
        check("with stdout and stderr in one file, as in the job log, the record comes before "
              "the line that points above at it",
              0 <= record_at < pointer_at, log_text)

    exits = {value for name, value in vars(job).items() if name.startswith("EXIT_")
             and isinstance(value, int)} - {job.EXIT_ALL_DONE, job.EXIT_ANOTHER_RUN_HOLDS_THE_LOCK,
                                            job.EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR,
                                            job.EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN}
    check("every exit code other than 0, 6, 7 and 9 is reached by a case here, and each such "
          "run opens a job failure task",
          set(opened_for_exit) == exits
          and all(tasks for runs in opened_for_exit.values() for tasks in runs),
          (sorted(exits), opened_for_exit))


def run_untestable_merge_cases():
    """A merge the mutation testing program finds a suite failing on, with no mutant applied."""
    failing_suite = "scripts/thing-test.py"
    untestable_step = {
        "exit": job.mutation_testing.EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD,
        "stderr": (f"mutation-testing: not run — a suite for scripts/thing.py fails on the "
                   f"unmutated head, so no mutant can be judged:\n"
                   f"{job.mutation_testing.SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX}"
                   f"{failing_suite}\nMake the suite pass at the head, then run this again.")}

    # The untestable merge is recorded, its task opened, and the merge after it tested in the
    # same run, from a state file an earlier version wrote without untestable_merges.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        alpha_list = fixture.seat("alpha")
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        untestable = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                                    author="alpha")
        after = fixture.commit("scripts/other.py", "def triple(x):\n    return x * 3\n",
                               author="alpha")
        completed = fixture.run({untestable: untestable_step,
                                 after: {"json": verdict(survived=[survivor()])}})
        record = fixture.records()[-1].read_text() if fixture.records() else ""
        tasks = job_failure_tasks(fixture)
        heads = [call[call.index("--head") + 1] for call in fixture.calls()]
        check("a merge whose suite fails on its unchanged code is recorded as untestable with "
              "that suite, and the run goes on to test the next merge and exits 0",
              completed.returncode == job.EXIT_ALL_DONE
              and heads == [untestable, after]
              and fixture.state_json()["last_tested_main_commit"] == after
              and fixture.state_json()[job.UNTESTABLE_MERGES_STATE_KEY]
              == {untestable: [failing_suite]}
              and task_files(alpha_list) == ["1.json"],
              (completed.returncode, completed.stderr, heads, fixture.state_json()))
        check("an untestable merge opens one job failure task naming the merge, the failing "
              "suite and a later commit's run with the merge's own parent as --base",
              [task["subject"] for task in tasks]
              == [job.untestable_merge_job_failure_task_subject(untestable)]
              and untestable in tasks[0]["description"]
              and failing_suite in tasks[0]["description"]
              and f"--base {start}" in tasks[0]["description"]
              and f"--head <that commit>" in tasks[0]["description"],
              tasks)
        check("the record names the untestable merge, its failing suite and its task, and "
              "counts it among the merges tested",
              f"UNTESTABLE: merge {untestable[:12]} (change scripts/thing.py): on its unchanged "
              f"code the suite(s) {failing_suite} fail" in record
              and f"JOB FAILURE TASK: opened task #{tasks[0]['id'] if tasks else ''} on "
                  f"{job.JOB_FAILURE_TASK_AGENT_SEAT}'s task list, "
                  f"{job.untestable_merge_job_failure_task_subject(untestable)}" in record
              and "merges tested: 2 of 2, 1 of them recorded as untestable" in record,
              record)
        calls_before = len(fixture.calls())
        completed = fixture.run({"recheck": {"exit": 1}})
        check("the next run does not try the untestable merge again",
              completed.returncode == job.EXIT_ALL_DONE
              and not any("--recorded-mutant-killed-check" not in call
                          for call in fixture.calls()[calls_before:]),
              (completed.returncode, fixture.calls()[calls_before:]))

    # The task cannot be opened: a failed step, the state left as it was.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        untestable = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n")
        after = fixture.commit("scripts/other.py", "def triple(x):\n    return x * 3\n")
        completed = fixture.run({untestable: untestable_step})
        heads = [call[call.index("--head") + 1] for call in fixture.calls()]
        check("an untestable merge whose job failure task cannot be opened stops the run at "
              "that merge, exit 4, with the state not advanced and no merge recorded as "
              "untestable",
              completed.returncode == job.EXIT_STEP_FAILED
              and heads == [untestable]
              and f"merge {untestable[:12]} (change scripts/thing.py): a suite fails on its "
                  f"unchanged code ({failing_suite}), so it is untestable, but its job failure "
                  f"task could not be opened" in completed.stderr
              and fixture.state_json() == {"last_tested_main_commit": start, "tasks_opened": {}},
              (completed.returncode, completed.stderr, heads, fixture.state_json()))


def run_carry_on_and_job_failure_task_cases():
    # A merge past the limit with no mutant judged: carried on, not recorded as tested, and
    # one job failure task, not a second on the next run.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "VALUE = 1\n")
        fixture.commit("scripts/other.py", "VALUE = 2\n")
        completed = fixture.run({merge: {"sleep": 30}}, timeout_seconds=1)
        record = fixture.records()[0].read_text() if fixture.records() else ""
        tasks = job_failure_tasks(fixture)
        sessions = fixture.state / job.COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME / merge
        call = fixture.calls()[0] if fixture.calls() else []
        check("a merge past the limit is carried on: exit 9, the state not advanced, no later "
              "merge run, and the record says so",
              completed.returncode == job.EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN
              and fixture.state_json()["last_tested_main_commit"] == start
              and len(fixture.calls()) == 1
              and f"CARRIED ON: merge {merge[:12]} (change scripts/thing.py) ran past the limit "
                  f"of 1 s with 0 mutant(s) judged" in record
              and "merges tested: 0 of 2" in record,
              f"rc={completed.returncode} calls={fixture.calls()} record={record} "
              f"err={completed.stderr}")
        check("the program is stopped with SIGTERM, so it can remove its worktrees",
              (fixture.root / "stopped-by-sigterm").exists())
        check("each merge's run is given a worker count and the merge's own kept sessions "
              "directory",
              call[call.index("--cosmic-ray-sessions-directory-kept-to-resume") + 1]
              == str(sessions)
              and int(call[call.index("--parallel-mutant-workers") + 1]) >= 1, call)
        check("a carried-on merge that judged no new mutant opens one job failure task saying "
              "what failed and what to do, named in the record",
              len(tasks) == 1 and tasks[0]["subject"]
              == f"Nightly full mutation pass judged no new mutant of merge {merge[:12]} in a "
                 f"night, before the per-merge time limit"
              and "systemd-run --user --unit=mutation-hand-run-" in tasks[0]["description"]
              and f"JOB FAILURE TASK: opened task #1 on {job.JOB_FAILURE_TASK_AGENT_SEAT}'s task "
                  f"list" in record, (tasks, record))
        workers = call[call.index("--parallel-mutant-workers") + 1] if call else None
        check("the hand run the task gives runs the merge as the nightly run did: in the same "
              "clone, with as many workers, resuming the merge's kept sessions",
              bool(tasks) and f"--checkout {fixture.clone.resolve()} " in tasks[0]["description"]
              and f"--parallel-mutant-workers {workers} " in tasks[0]["description"]
              and f"--cosmic-ray-sessions-directory-kept-to-resume {sessions}"
                  in tasks[0]["description"], tasks)
        completed = fixture.run({merge: {"sleep": 30}}, timeout_seconds=1)
        record = fixture.records()[-1].read_text()
        check("the next run with no progress opens no second task while the first is open",
              len(job_failure_tasks(fixture)) == 1
              and "already open, so none opened: task #1" in record, record)
        task_file = fixture.tasks / f"nedschorus-{job.JOB_FAILURE_TASK_AGENT_SEAT}-tasks" / "1.json"
        task_file.write_text(json.dumps(dict(json.loads(task_file.read_text()),
                                             status="completed")))
        fixture.run({merge: {"sleep": 30}}, timeout_seconds=1)
        check("once that task is completed, the same failure opens a new task",
              [task["status"] for task in job_failure_tasks(fixture)] == ["completed", "pending"],
              job_failure_tasks(fixture))

    # A carried-on merge that judged new mutants opens no task; once tested, its kept sessions
    # are removed by the next run.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "VALUE = 1\n")
        completed = fixture.run({merge: {"sleep": 30, "judged_in_kept_session": 3}},
                                timeout_seconds=2)
        record = fixture.records()[0].read_text() if fixture.records() else ""
        check("a carried-on merge with new mutants judged: exit 9, no job failure task, and the "
              "record counts them, the skipped ones left out",
              completed.returncode == job.EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN
              and job_failure_tasks(fixture) == []
              and "with 3 mutant(s) judged, 3 of them in this run" in record,
              f"rc={completed.returncode} record={record} err={completed.stderr}")
        completed = fixture.run({merge: {"sleep": 30, "judged_in_kept_session": 2}},
                                timeout_seconds=2)
        record = fixture.records()[-1].read_text()
        check("a second night counts the mutants judged before it apart from its own",
              completed.returncode == job.EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN
              and job_failure_tasks(fixture) == []
              and "with 5 mutant(s) judged, 2 of them in this run" in record,
              f"rc={completed.returncode} record={record}")
        fixture.run({merge: {"sleep": 30, "judged_in_kept_session": 1,
                             "kept_session_started_again": True}}, timeout_seconds=2)
        check("a night that ends with fewer mutants judged than it began with judged no new "
              "one, and gets a task",
              [task["subject"] for task in job_failure_tasks(fixture)]
              == [f"Nightly full mutation pass judged no new mutant of merge {merge[:12]} in a "
                  f"night, before the per-merge time limit"], job_failure_tasks(fixture))
        completed = fixture.run({merge: {"json": verdict()}})
        record = fixture.records()[-1].read_text()
        sessions = fixture.state / job.COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME
        check("the next run says how many mutants its kept sessions held, and records the merge "
              "as tested",
              completed.returncode == 0
              and f"merge {merge[:12]}: " in record
              and "1 mutant(s) already judged in its kept sessions" in record
              and fixture.state_json()["last_tested_main_commit"] == merge,
              f"rc={completed.returncode} record={record} err={completed.stderr}")
        fixture.run()
        check("a run removes the kept sessions of a merge no longer waiting to be tested",
              not (sessions / merge).exists(), list(sessions.iterdir()))

    # A kept session that cannot be read stops the run.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "VALUE = 1\n")
        sessions = (fixture.state / job.COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME
                    / merge)
        sessions.mkdir(parents=True)
        (sessions / "garbage.sqlite").write_text("not a database")
        completed = fixture.run({merge: {"json": verdict()}})
        tasks = job_failure_tasks(fixture)
        check("a kept session that cannot be read: exit 4, a job failure task with the failure, "
              "and the merge not recorded as tested",
              completed.returncode == job.EXIT_STEP_FAILED
              and fixture.calls() == []
              and fixture.state_json()["last_tested_main_commit"] == start
              and len(tasks) == 1
              and tasks[0]["subject"].startswith(
                  "Nightly full mutation pass stopped at a failed step: the kept cosmic-ray "
                  "session")
              and f"Delete the session file {sessions / 'garbage.sqlite'} on ned-box, and no other "
                  f"file" in tasks[0]["description"],
              f"rc={completed.returncode} tasks={tasks} err={completed.stderr}")

    # A failed step opens a job failure task; the same failure again opens no second one.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "VALUE = 1\n")
        step = {merge: {"exit": 2, "stderr": "mutation-testing: not run — cosmic-ray is missing"}}
        completed = fixture.run(step)
        tasks = job_failure_tasks(fixture)
        check("a failed step: exit 4 and one job failure task whose subject is the failure's "
              "first line and whose description holds the whole failure and the record",
              completed.returncode == job.EXIT_STEP_FAILED and len(tasks) == 1
              and tasks[0]["subject"] == f"Nightly full mutation pass stopped at a failed step: "
                                         f"merge {merge[:12]} (change scripts/thing.py): the "
                                         f"mutation testing program exited 2 without saying "
                                         f"whether each mutant was killed. The next run tries "
                                         f"this merge again. It printed:"[
                                             :len("Nightly full mutation pass stopped at a "
                                                  "failed step: ") + 200]
              and "It printed:\n    mutation-testing: not run — cosmic-ray is missing\nIf it "
                  "fails the same way again" in tasks[0]["description"]
              and str(fixture.records()[0]) in tasks[0]["description"],
              f"rc={completed.returncode} tasks={tasks}")
        fixture.run(step)
        check("the same failed step again opens no second task", len(job_failure_tasks(fixture))
              == 1, job_failure_tasks(fixture))

    # An error the program does not handle still writes the record, opens a task with its
    # traceback, and exits 4.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.state.mkdir(parents=True)
        (fixture.state / job.STATE_FILE_NAME).write_text(json.dumps({
            "last_tested_main_commit": start, "tasks_opened": {"k": {}}}))
        completed = fixture.run()
        record = fixture.records()[0].read_text() if fixture.records() else ""
        tasks = job_failure_tasks(fixture)
        check("an error the program does not handle: exit 4, the record and a job failure task "
              "carry its traceback",
              completed.returncode == job.EXIT_STEP_FAILED
              and "FAILED: the run raised KeyError: 'agent_seat', which this program does not "
                  "handle" in record and "Traceback (most recent call last)" in record
              and len(tasks) == 1 and "Traceback" in tasks[0]["description"],
              f"rc={completed.returncode} record={record} err={completed.stderr}")

    # Merges still untested three days after their merge commits share one task, whose
    # description each run rewrites with the count and the oldest.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        old = fixture.commit("scripts/thing.py", "VALUE = 1\n")
        days_ago = int(time.time()) - job.MERGE_STILL_UNTESTED_TASK_OPENED_AFTER_SECONDS_SINCE_MERGE - 60
        (fixture.work / "scripts" / "other.py").write_text("VALUE = 2\n")
        git(fixture.work, "add", "-A")
        subprocess.run(["git", "-C", str(fixture.work), "commit", "-q", "-m", "older"],
                       env={**os.environ, "GIT_COMMITTER_DATE": f"{days_ago} +0000",
                            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"},
                       check=True)
        git(fixture.work, "push", "-q", "origin", "HEAD:main")
        three_days_old = git(fixture.work, "rev-parse", "HEAD")
        completed = fixture.run({old: {"sleep": 30, "judged_in_kept_session": 1}},
                                timeout_seconds=2)
        tasks = job_failure_tasks(fixture)
        warnings = [task for task in tasks if task["subject"]
                    == job.MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT]
        check("a merge waiting behind a carried-on one three days after its merge commit gets "
              "the one untested-merges task, naming it as the oldest of 1; a newer one does not",
              completed.returncode == job.EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN
              and len(warnings) == 1
              and warnings[0]["description"].startswith("1 merge(s) into main")
              and f"The oldest is merge {three_days_old}," in warnings[0]["description"],
              f"rc={completed.returncode} tasks={tasks} err={completed.stderr}")
        (fixture.work / "scripts" / "third.py").write_text("VALUE = 3\n")
        git(fixture.work, "add", "-A")
        subprocess.run(["git", "-C", str(fixture.work), "commit", "-q", "-m", "older too"],
                       env={**os.environ, "GIT_COMMITTER_DATE": f"{days_ago + 1} +0000",
                            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"},
                       check=True)
        git(fixture.work, "push", "-q", "origin", "HEAD:main")
        completed = fixture.run({old: {"sleep": 30, "judged_in_kept_session": 1}},
                                timeout_seconds=2)
        tasks = job_failure_tasks(fixture)
        warnings = [task for task in tasks if task["subject"]
                    == job.MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT]
        check("a second three-day-old merge opens no second task: the one open task's "
              "description now counts 2, the oldest unchanged",
              len(warnings) == 1
              and warnings[0]["description"].startswith("2 merge(s) into main")
              and f"The oldest is merge {three_days_old}," in warnings[0]["description"],
              f"rc={completed.returncode} tasks={tasks} err={completed.stderr}")
        # With the task list gone, neither of this run's two tasks can be opened.
        for path in (fixture.tasks / f"nedschorus-{job.JOB_FAILURE_TASK_AGENT_SEAT}-tasks").iterdir():
            path.unlink()
        (fixture.tasks / f"nedschorus-{job.JOB_FAILURE_TASK_AGENT_SEAT}-tasks").rmdir()
        completed = fixture.run({old: {"sleep": 30}}, timeout_seconds=1)
        record = fixture.records()[-1].read_text()
        failed = [line for line in record.splitlines()
                  if line.startswith("FAILED: no job failure task could be opened")]
        check("each task that cannot be opened is named in the record, and the run exits 4",
              completed.returncode == job.EXIT_STEP_FAILED and len(failed) == 2
              and "judged no new mutant" in failed[0] and "three days" in failed[1]
              and "2 task(s) for a failure of this run could not be opened" in completed.stderr,
              f"rc={completed.returncode} failed={failed} err={completed.stderr}")

    # A step that fails before any merge is tested still has the merges three days untested
    # reported.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        start = git(fixture.work, "rev-parse", "HEAD")
        days_ago = int(time.time()) - job.MERGE_STILL_UNTESTED_TASK_OPENED_AFTER_SECONDS_SINCE_MERGE - 60
        (fixture.work / "scripts" / "other.py").parent.mkdir(parents=True, exist_ok=True)
        (fixture.work / "scripts" / "other.py").write_text("VALUE = 2\n")
        git(fixture.work, "add", "-A")
        subprocess.run(["git", "-C", str(fixture.work), "commit", "-q", "-m", "older"],
                       env={**os.environ, "GIT_COMMITTER_DATE": f"{days_ago} +0000",
                            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"},
                       check=True)
        git(fixture.work, "push", "-q", "origin", "HEAD:main")
        three_days_old = git(fixture.work, "rev-parse", "HEAD")
        fixture.state.mkdir(parents=True)
        # A state naming a survivor task with no agent-seat makes the step after the merges
        # are listed fail.
        (fixture.state / job.STATE_FILE_NAME).write_text(json.dumps({
            "last_tested_main_commit": start, "tasks_opened": {"k": {}}}))
        completed = fixture.run()
        subjects = [task["subject"] for task in job_failure_tasks(fixture)]
        warnings = [task for task in job_failure_tasks(fixture) if task["subject"]
                    == job.MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT]
        check("a step that fails before any merge is tested: exit 4, its task, and the "
              "untested-merges task naming the merge three days untested",
              completed.returncode == job.EXIT_STEP_FAILED and len(subjects) == 2
              and subjects[0].startswith("Nightly full mutation pass stopped at a failed step")
              and len(warnings) == 1
              and f"The oldest is merge {three_days_old}," in warnings[0]["description"],
              f"rc={completed.returncode} subjects={subjects} err={completed.stderr}")

    # A session whose writer was killed part-way through a write leaves a hot journal; the
    # count rolls it back and counts what was committed.
    with tempfile.TemporaryDirectory() as scratch:
        session = Path(scratch) / "kept.sqlite"
        connection = sqlite3.connect(session)
        connection.execute("CREATE TABLE work_results (job_id, worker_outcome)")
        connection.executemany("INSERT INTO work_results VALUES (?, ?)",
                               [("a", "NORMAL"), ("b", "SKIPPED"), ("c", "EXCEPTION")])
        connection.commit()
        connection.close()
        ready = Path(scratch) / "ready"
        writer = subprocess.Popen([sys.executable, "-c", (
            "import pathlib, sqlite3, sys, time\n"
            "connection = sqlite3.connect(sys.argv[1], isolation_level=None)\n"
            "connection.execute('PRAGMA cache_size=5')\n"
            "connection.execute('BEGIN IMMEDIATE')\n"
            "for number in range(50000):\n"
            "    connection.execute('INSERT INTO work_results VALUES (?, ?)', "
            "('x' * 50 + str(number), 'NORMAL'))\n"
            "pathlib.Path(sys.argv[2]).write_text('')\n"
            "time.sleep(60)\n"), str(session), str(ready)])
        deadline = time.monotonic() + 60
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        writer.kill()
        writer.wait()
        journal_left = session.with_name(session.name + "-journal").exists()
        count = job.count_of_mutants_judged_in_kept_cosmic_ray_sessions(Path(scratch))
        check("a kept session left with a hot journal by a writer killed part-way is rolled back "
              "and counted, its skipped mutants left out",
              journal_left and count == 2, (journal_left, count))

    # mutant_worker_count_for_free_cores: the cores less the load, from 1 to the cores.
    counts = [job.mutant_worker_count_for_free_cores(cores, load)
              for cores, load in ((16, 3.5), (16, 40.0), (16, 0.0), (1, 0.0))]
    check("the worker count is the cores less the 1-minute load average, at least 1, at most "
          "the cores", counts == [12, 1, 16, 1], counts)


def run_last_line_said_cases():
    kept = (f"{job.mutation_testing.TEST_SUITE_RUNNER_LOGS_KEPT_LINE_PREFIX}/tmp/x; "
            f"remove that directory once you have read them.")
    check("last_line_said quotes the refusal on standard error, not the line naming where the "
          "suite runner's logs are kept after it",
          job.last_line_said("MUTATING a.py", f"refused: the suites fail\n{kept}\n")
          == "refused: the suites fail")
    check("last_line_said falls back to standard output's last line when standard error holds "
          "only the kept-logs line",
          job.last_line_said("MUTATING a.py with b-test.py\n", f"{kept}\n")
          == "MUTATING a.py with b-test.py")
    check("last_line_said says nothing when neither stream holds another line",
          job.last_line_said("", f"{kept}\n") == "nothing")


def run_cases():
    run_last_line_said_cases()
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
        diff_file = (fixture.log_store / job.RECORDS_DIRECTORY_NAME
                     / job.SURVIVING_MUTANT_DIFFS_DIRECTORY_NAME
                     / f"{job.mutant_key(survivor())}.diff")
        description = task.get("description", "")
        check("merges: the survivor's diff is written beside the records, for the recorded "
              "mutant killed check",
              diff_file.is_file() and diff_file.read_text() == SURVIVOR_DIFF, diff_file)
        check("merges: the task gives this task's command, the recorded mutant killed check with "
              "the mutant's diff file, and says to open the pull request with the command's "
              "output, running the command on ned-box",
              f"\nThis task's command: python3 scripts/{job.MUTATION_TESTING_PROGRAM.name} "
              f"--recorded-mutant-killed-check {diff_file}\n" in description
              and "\nIf a test can tell a mutant from the code: write that test, run this task's "
                  "command on your branch, and open a pull request with the test, putting the "
                  "command's output in its description.\n" in description
              and "\nRun the command on ned-box at the root of your checkout with the test "
                  "committed.\n" in description
              and "by hand" not in description, description)
        check("merges: the task's last line says to leave it open for the nightly mutation pass, "
              "and no line says to mark it completed",
              description.endswith(
                  "\nLeave this task open: the nightly mutation pass completes it once no mutant "
                  "it lists survives on main, or the line is gone or ends with a `# pragma: no "
                  "mutate` comment.")
              and "mark this task completed" not in description, description)
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
         "exited 2 without saying whether each mutant was killed. The next run tries this merge "
         "again. It printed:\n    mutation-testing: not run — cosmic-ray is missing"),
        # git puts the cause before its last line.
        ("the mutation testing program exits 2 with the cause before its last line of stderr",
         {"exit": 2, "stderr": "mutation-testing: git worktree add failed (exit 128): "
                               "Preparing worktree (detached HEAD 557f938)\n"
                               "error: unable to write file README: No space left on device\n"
                               "fatal: Could not reset index file to revision 'HEAD'."}, None,
         "It printed:\n    mutation-testing: git worktree add failed (exit 128): Preparing "
         "worktree (detached HEAD 557f938)\n    error: unable to write file README: No space "
         "left on device\n    fatal: Could not reset index file to revision 'HEAD'.\n"),
        # Above EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD, as when a signal stopped it.
        ("the mutation testing program exits 143",
         {"exit": 143, "stderr": "stopped"}, None,
         "exited 143 without saying whether each mutant was killed. The next run tries this "
         "merge again."),
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
                  and f"merge {merge[:12]} (change scripts/thing.py): " in record
                  and "The next run tries this merge again" in record
                  and fixture.state_json()["last_tested_main_commit"] == start,
                  f"rc={completed.returncode} record={record} err={completed.stderr}")
            crash_tasks = [json.loads(path.read_text()) for path in
                           (fixture.tasks / f"nedschorus-{job.JOB_FAILURE_TASK_AGENT_SEAT}-tasks"
                            ).glob("*.json")]
            check(f"{case_name}: no job failure task list, so the task is named on stderr "
                  f"as not opened", "could not be opened on fleet-restart-at-login's task list"
                  in completed.stderr and not crash_tasks, (completed.stderr, crash_tasks))

    run_carry_on_and_job_failure_task_cases()
    run_untestable_merge_cases()

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
              and f"merge {merge[:12]}: no task could be opened on merge-lane-2's task list"
              in completed.stderr
              and "nedschorus-merge-lane-2-tasks does not exist" in completed.stderr
              and fixture.state_json()["last_tested_main_commit"] == start,
              f"rc={completed.returncode} err={completed.stderr}")

    # The survivor's diff cannot be written: no task is opened and the merge is not recorded as
    # tested.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        (fixture.log_store / job.RECORDS_DIRECTORY_NAME).mkdir(parents=True)
        (fixture.log_store / job.RECORDS_DIRECTORY_NAME
         / job.SURVIVING_MUTANT_DIFFS_DIRECTORY_NAME).write_text("a file, not a directory")
        completed = fixture.run({merge: {"json": verdict(
            survived=[survivor(), survivor(2, "core/ReplaceBinaryOperator_Add_Sub")])}})
        check("a survivor's diff that cannot be written stops the run at that merge, exit 4, "
              "naming the path that cannot be written, with no task opened",
              completed.returncode == job.EXIT_STEP_FAILED
              and f"merge {merge[:12]}: no task could be opened on alpha's task list"
              in completed.stderr
              and f"FileExistsError: [Errno 17] File exists: "
                  f"'{fixture.log_store / job.RECORDS_DIRECTORY_NAME / job.SURVIVING_MUTANT_DIFFS_DIRECTORY_NAME}'"
                  in completed.stderr
              and task_files(alpha_list) == []
              and fixture.state_json()["last_tested_main_commit"] == start,
              f"rc={completed.returncode} err={completed.stderr} tasks={task_files(alpha_list)}")

    # A run stopped after one survivor's task is opened keeps that task in the state, so the
    # next run, which tries the merge again, opens no second task for it.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n", author="alpha")
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="nobody")
        alpha_list = fixture.seat("alpha")
        plan = {merge: {"json": verdict(survived=[survivor(), survivor(3, "core/NumberReplacer")])}}
        completed = fixture.run(plan)
        check("a run stopped at the second survivor's task records the first task in the state",
              completed.returncode == job.EXIT_STEP_FAILED
              and task_files(alpha_list) == ["1.json"]
              and list(fixture.state_json()["tasks_opened"].values())
              == [{"agent_seat": "alpha", "task_id": 1}]
              and fixture.state_json()["last_tested_main_commit"] == start,
              (completed.returncode, task_files(alpha_list), fixture.state_json()))
        fixture.seat(job.SURVIVOR_TASK_AGENT_SEAT_WHEN_LINE_AUTHOR_IS_RETIRED_OR_UNKNOWN)
        completed = fixture.run(plan)
        check("the next run opens no second task for the first survivor",
              completed.returncode == 0 and task_files(alpha_list) == ["1.json"],
              (completed.returncode, task_files(alpha_list), completed.stderr))

    # A task linked into place before the .highwatermark write failed is not in the state; the
    # next run finds it on the list by the mutant's diff file and opens no second task.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        (alpha_list / (job.TASK_HIGH_WATER_MARK_FILE_NAME + ".partial")).mkdir()
        plan = {merge: {"json": verdict(survived=[survivor()])}}
        completed = fixture.run(plan)
        check("a .highwatermark that cannot be written after the task is linked stops the run, "
              "exit 4, with the task on the list and not in the state",
              completed.returncode == job.EXIT_STEP_FAILED
              and task_files(alpha_list) == ["1.json"]
              and fixture.state_json()["tasks_opened"] == {}
              and fixture.state_json()["last_tested_main_commit"] == start,
              (completed.returncode, task_files(alpha_list), fixture.state_json(),
               completed.stderr))
        (alpha_list / (job.TASK_HIGH_WATER_MARK_FILE_NAME + ".partial")).rmdir()
        completed = fixture.run(plan)
        key = job.mutant_key(survivor())
        check("the next run finds that task by the mutant's diff file, opens no second one, "
              "and records it in the state",
              completed.returncode == 0 and task_files(alpha_list) == ["1.json"]
              and fixture.state_json()["tasks_opened"].get(key)
              == {"agent_seat": "alpha", "task_id": 1}
              and "already given task #1 on alpha's task list"
              in fixture.records()[-1].read_text(),
              (completed.returncode, task_files(alpha_list), fixture.state_json(),
               completed.stderr))

        # Each run checks that the tasks it opened still hold their survivors, and reports, once,
        # each that does not and is not completed; it opens no task in its place.
        (alpha_list / "1.json").write_text(json.dumps({"id": "1", "description": "rewritten"}))
        diff_file = job.mutant_diff_file_path(fixture.log_store, key)
        completed = fixture.run()
        check("a task rewritten so it no longer names its mutant is reported in the record and "
              "on stderr, no task is opened, the state stops naming it, and the run exits 7",
              completed.returncode == job.EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR
              and task_files(alpha_list) == ["1.json"]
              and fixture.state_json()["tasks_opened"] == {}
              and f"TASK LOST: task #1 on alpha's task list ({alpha_list / '1.json'}) no "
                  f"longer holds the surviving mutant {diff_file}: its description no longer "
                  f"names the mutant's diff file" in fixture.records()[-1].read_text()
              and "1 task(s) that an earlier run opened" in completed.stderr
              and "later runs do not report them again" in completed.stderr,
              (completed.returncode, task_files(alpha_list), completed.stderr))
        completed = fixture.run()
        check("a lost task already reported is not reported again, and the run exits 0",
              completed.returncode == 0 and "TASK LOST" not in fixture.records()[-1].read_text()
              and task_files(alpha_list) == ["1.json"],
              (completed.returncode, completed.stderr))

    # A task whose file is gone is reported once; a completed task is dropped from the state
    # without a report, and a pending one that holds its mutant is kept.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        start = git(fixture.work, "rev-parse", "HEAD")
        fixture.set_last(start)
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="alpha")
        second_survivor = survivor(1, "core/ReplaceBinaryOperator_Add_Sub")
        third_survivor = survivor(3, "core/ReplaceBinaryOperator_Add_Div")
        completed = fixture.run(
            {merge: {"json": verdict(survived=[survivor(), second_survivor, third_survivor])}})
        check("three survivors on three lines get tasks 1, 2 and 3",
              completed.returncode == 0
              and task_files(alpha_list) == ["1.json", "2.json", "3.json"],
              (completed.returncode, task_files(alpha_list), completed.stderr))
        keys = {given["task_id"]: key
                for key, given in fixture.state_json()["tasks_opened"].items()}
        (alpha_list / "1.json").unlink()
        finished = json.loads((alpha_list / "2.json").read_text())
        finished["status"] = "completed"
        (alpha_list / "2.json").write_text(json.dumps(finished))
        completed = fixture.run()
        record = fixture.records()[-1].read_text()
        check("a missing task file is reported, a completed task is not, and the state keeps "
              "only the pending task that holds its mutant",
              completed.returncode == job.EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR
              and "TASK LOST: task #1 on alpha's task list" in record
              and "the task file cannot be read (FileNotFoundError" in record
              and "task #2" not in record
              and task_files(alpha_list) == ["2.json", "3.json"]
              and fixture.state_json()["tasks_opened"]
              == {keys[3]: {"agent_seat": "alpha", "task_id": 3}},
              (completed.returncode, record, fixture.state_json()))
        (alpha_list / "2.json").unlink()
        completed = fixture.run()
        check("a completed task deleted later, as a session-handoff does, is not reported",
              completed.returncode == 0 and "TASK LOST" not in fixture.records()[-1].read_text(),
              (completed.returncode, completed.stderr))
        (alpha_list / "3.json").write_text(
            json.dumps({"id": "3", "status": "completed", "description": "rewritten"}))
        completed = fixture.run()
        check("a completed task whose description no longer names its mutant is dropped from "
              "the state without a report, and the run exits 0",
              completed.returncode == 0 and "TASK LOST" not in fixture.records()[-1].read_text()
              and fixture.state_json()["tasks_opened"] == {},
              (completed.returncode, completed.stderr, fixture.state_json()))

    # A mutant whose task file is gone, as after a fold of its task into another and the
    # handoff prune of the completed task, follows the one open task that names its diff file;
    # with two such tasks it is reported lost.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="alpha")
        completed = fixture.run({merge: {"json": verdict(
            survived=[survivor(), survivor(1, "core/ReplaceBinaryOperator_Add_Sub"),
                      survivor(3, "core/ReplaceBinaryOperator_Add_Div")])}})
        keys = {given["task_id"]: key
                for key, given in fixture.state_json()["tasks_opened"].items()}
        folded = json.loads((alpha_list / "2.json").read_text())
        folded["description"] += f"\n{keys[1]}.diff"
        (alpha_list / "2.json").write_text(json.dumps(folded))
        (alpha_list / "1.json").unlink()
        completed = fixture.run()
        record = fixture.records()[-1].read_text()
        check("a mutant whose task file is gone moves to the one open task naming its diff "
              "file, is not reported lost, and the run exits 0",
              completed.returncode == 0 and "TASK LOST" not in record
              and f"TASK MOVED: the surviving mutant "
                  f"{job.mutant_diff_file_path(fixture.log_store, keys[1])} is now held by task "
                  f"#2 on alpha's task list, not task #1" in record
              and fixture.state_json()["tasks_opened"].get(keys[1])
              == {"agent_seat": "alpha", "task_id": 2},
              (completed.returncode, record, fixture.state_json()))
        for task_id in (2, 3):
            other = json.loads((alpha_list / f"{task_id}.json").read_text())
            other["description"] = f"{keys[1]}.diff {keys[task_id]}.diff"
            (alpha_list / f"{task_id}.json").write_text(json.dumps(other))
        (alpha_list / "2.json").unlink()
        (alpha_list / "4.json").write_text(json.dumps({"description": f"{keys[1]}.diff"}))
        completed = fixture.run()
        record = fixture.records()[-1].read_text()
        check("a mutant whose task file is gone and whose diff file two open tasks name is "
              "reported lost, and the run exits 7",
              completed.returncode == job.EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR
              and "TASK LOST: task #2 on alpha's task list" in record
              and "TASK MOVED" not in record
              and keys[1] not in fixture.state_json()["tasks_opened"],
              (completed.returncode, record, fixture.state_json()))

    # A fold seen before the handoff prune: the task the mutant left is still on the list,
    # marked completed, and the one open task it moved to names its diff file.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="alpha")
        completed = fixture.run({merge: {"json": verdict(
            survived=[survivor(), survivor(1, "core/ReplaceBinaryOperator_Add_Sub"),
                      survivor(3, "core/ReplaceBinaryOperator_Add_Div")])}})
        keys = {given["task_id"]: key
                for key, given in fixture.state_json()["tasks_opened"].items()}
        folded = json.loads((alpha_list / "2.json").read_text())
        folded["description"] += f"\n{keys[1]}.diff"
        (alpha_list / "2.json").write_text(json.dumps(folded))
        left = json.loads((alpha_list / "1.json").read_text())
        left["status"] = "completed"
        (alpha_list / "1.json").write_text(json.dumps(left))
        completed = fixture.run()
        record = fixture.records()[-1].read_text()
        check("a mutant whose task is marked completed, while the one open task naming its diff "
              "file holds it, moves to that task, and the run exits 0",
              completed.returncode == 0 and "TASK LOST" not in record
              and f"TASK MOVED: the surviving mutant "
                  f"{job.mutant_diff_file_path(fixture.log_store, keys[1])} is now held by task "
                  f"#2 on alpha's task list, not task #1 (it is marked completed)" in record
              and fixture.state_json()["tasks_opened"].get(keys[1])
              == {"agent_seat": "alpha", "task_id": 2},
              (completed.returncode, record, fixture.state_json()))

    # The same fold, on a night whose recheck gives no verdicts and that has no merge to test:
    # only step 4's own write of the state keeps the move.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="alpha")
        completed = fixture.run({merge: {"json": verdict(
            survived=[survivor(), survivor(3, "core/ReplaceBinaryOperator_Add_Div")])}})
        keys = {given["task_id"]: key
                for key, given in fixture.state_json()["tasks_opened"].items()}
        folded = json.loads((alpha_list / "2.json").read_text())
        folded["description"] += f"\n{keys[1]}.diff"
        (alpha_list / "2.json").write_text(json.dumps(folded))
        left = json.loads((alpha_list / "1.json").read_text())
        left["status"] = "completed"
        (alpha_list / "1.json").write_text(json.dumps(left))
        completed = fixture.run({"recheck": {"no_verdicts": True, "exit": 2}})
        check("a mutant moved at step 4 stays moved in the state file when the recheck gives no "
              "verdicts and no merge is tested, and the run exits 8",
              completed.returncode == job.EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS
              and fixture.state_json()["tasks_opened"].get(keys[1])
              == {"agent_seat": "alpha", "task_id": 2},
              (completed.returncode, fixture.records()[-1].read_text(), fixture.state_json()))

    # A fold seen before the handoff prune, where two open tasks name the mutant the completed
    # task held: which one holds it cannot be told.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="alpha")
        completed = fixture.run({merge: {"json": verdict(
            survived=[survivor(), survivor(1, "core/ReplaceBinaryOperator_Add_Sub"),
                      survivor(3, "core/ReplaceBinaryOperator_Add_Div")])}})
        keys = {given["task_id"]: key
                for key, given in fixture.state_json()["tasks_opened"].items()}
        for task_id in (2, 3):
            other = json.loads((alpha_list / f"{task_id}.json").read_text())
            other["description"] += f"\n{keys[1]}.diff"
            (alpha_list / f"{task_id}.json").write_text(json.dumps(other))
        left = json.loads((alpha_list / "1.json").read_text())
        left["status"] = "completed"
        (alpha_list / "1.json").write_text(json.dumps(left))
        completed = fixture.run()
        record = fixture.records()[-1].read_text()
        check("a mutant whose task is marked completed and whose diff file two open tasks name "
              "is reported lost, saying the task is completed, leaves the state, and the run "
              "exits 7",
              completed.returncode == job.EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR
              and f"TASK LOST: task #1 on alpha's task list ({alpha_list / '1.json'}) no longer "
                  f"holds the surviving mutant "
                  f"{job.mutant_diff_file_path(fixture.log_store, keys[1])}: it is marked "
                  f"completed" in record
              and "TASK MOVED" not in record
              and keys[1] not in fixture.state_json()["tasks_opened"],
              (completed.returncode, record, fixture.state_json()))

    # A task file holding JSON that is not an object is a task that no longer holds its mutant.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        completed = fixture.run({merge: {"json": verdict(survived=[survivor()])}})
        (alpha_list / "1.json").write_text("[]")
        completed = fixture.run()
        check("a task file holding a JSON list is reported as lost, and the run exits 7",
              completed.returncode == job.EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR
              and "TASK LOST: task #1 on alpha's task list" in fixture.records()[-1].read_text()
              and fixture.state_json()["tasks_opened"] == {},
              (completed.returncode, completed.stderr))

    # A run killed while mutation testing has already reported its lost task in a record; and
    # a record that cannot be written leaves the lost task in the state for the next run.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        completed = fixture.run({merge: {"json": verdict(survived=[survivor()])}})
        key = job.mutant_key(survivor())
        check("a survivor gets task 1", completed.returncode == 0
              and task_files(alpha_list) == ["1.json"], (completed.returncode, completed.stderr))
        (alpha_list / "1.json").unlink()
        records_directory = fixture.log_store / job.RECORDS_DIRECTORY_NAME
        held_aside = fixture.root / "records-held-aside"
        records_directory.rename(held_aside)
        records_directory.parent.joinpath(job.RECORDS_DIRECTORY_NAME).write_text("not a directory")
        completed = fixture.run()
        check("a record that cannot be written before the state forgets a lost task stops the "
              "run, exit 5, with the state still naming the task",
              completed.returncode == job.EXIT_RECORD_NOT_WRITTEN
              and "TASK LOST: task #1" in completed.stdout
              and "next run reports them again" in completed.stdout
              and key in fixture.state_json()["tasks_opened"]
              and "later runs do not report them again" not in completed.stderr,
              (completed.returncode, completed.stdout, completed.stderr, fixture.state_json()))
        (fixture.log_store / job.RECORDS_DIRECTORY_NAME).unlink()
        held_aside.rename(records_directory)
        check("no record names the lost task before the next run",
              not any("TASK LOST" in path.read_text() for path in fixture.records()),
              [path.read_text() for path in fixture.records()])
        later = fixture.commit("scripts/other.py", "VALUE = 1\n", author="alpha")
        fixture.plan_file.write_text(json.dumps({later: {"sleep": 60}}))
        calls_before = len(fixture.calls())
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--clone", str(fixture.clone),
             "--log-store-root", str(fixture.log_store), "--state-directory", str(fixture.state),
             "--task-lists-directory", str(fixture.tasks),
             "--agent-seats-directory", str(fixture.agents),
             "--cosmic-ray-venv", str(fixture.venv),
             "--mutation-testing-program", str(fixture.program)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, PLAN_VARIABLE: str(fixture.plan_file)}, start_new_session=True)
        deadline = time.monotonic() + 120
        while len(fixture.calls()) == calls_before and time.monotonic() < deadline \
                and process.poll() is None:
            time.sleep(0.1)
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        # Runs started in the same second share a record file, so look for the line, not a file.
        recorded = [path.read_text() for path in fixture.records()]
        check("a run killed while mutation testing, after the state stopped naming the lost "
              "task, has already written a record naming it",
              any("TASK LOST: task #1" in text for text in recorded)
              and fixture.state_json()["tasks_opened"] == {},
              (recorded, fixture.state_json()))

    # The survivors of a line get one task between them, and a line with a task not marked
    # completed, in the subject an earlier version wrote or in this one, gets no second task.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py",
                               "def double(x):\n    return x + x\nVALUE = 1\n", author="alpha")
        for task_id, line, status in [(6, 1, "pending"), (7, 21, "pending"), (8, 3, "completed")]:
            (alpha_list / f"{task_id}.json").write_text(json.dumps({
                "id": str(task_id), "status": status, "description": "an earlier version's",
                "subject": f"Surviving mutant in scripts/thing.py:{line}: add a test that kills "
                           f"it, or record why no test can"}))
        same_operator = dict(survivor(), diff=SURVIVOR_DIFF.replace("x * x", "x * 1"))
        line_two = [survivor(), survivor(2, "core/ReplaceBinaryOperator_Add_Sub"), same_operator]
        completed = fixture.run({merge: {"json": verdict(
            survived=[*line_two, survivor(1, "core/NumberReplacer"),
                      survivor(3, "core/ReplaceUnaryOperator_Delete_Not")])}})
        task = json.loads((alpha_list / "9.json").read_text()) \
            if (alpha_list / "9.json").exists() else {}
        description = task.get("description", "")
        diff_files = [job.mutant_diff_file_path(fixture.log_store, job.mutant_key(mutant))
                      for mutant in line_two]
        check("the three survivors of one line get one task, naming how many survived and "
              "each operator with its count, and one command with every mutant's diff file",
              completed.returncode == 0
              and task_files(alpha_list) == ["10.json", "6.json", "7.json", "8.json", "9.json"]
              and task.get("subject", "").startswith("Surviving mutants in scripts/thing.py:2: 3;")
              and "core/ReplaceBinaryOperator_Add_Mul (2), core/ReplaceBinaryOperator_Add_Sub (1)"
                  in description
              and "+    return x * 1" in description
              and f"This task's command: {job.survivor_task_recorded_mutant_killed_check_command_line(sorted(diff_files))}\n"
                  in description
              and all(path.is_file() for path in diff_files)
              and all(fixture.state_json()["tasks_opened"].get(job.mutant_key(mutant))
                      == {"agent_seat": "alpha", "task_id": 9} for mutant in line_two),
              (completed.returncode, completed.stderr, task_files(alpha_list), task,
               fixture.state_json()))
        record = fixture.records()[-1].read_text()
        line_one = survivor(1, "core/NumberReplacer")
        line_one_diff_file = job.mutant_diff_file_path(fixture.log_store, job.mutant_key(line_one))
        task_six = json.loads((alpha_list / "6.json").read_text())
        check("a line with a pending task in an earlier version's subject gets no second task: "
              "its survivor is added to that task, which is rewritten with this version's "
              "subject and one command, and the state names the task for it; a completed task, "
              "and a pending one for line 21, do not stop the task for line 3",
              "SURVIVED scripts/thing.py:1 core/NumberReplacer: added to task #6, open for this "
              "line, on alpha's task list" in record
              and task_six["subject"].startswith("Surviving mutants in scripts/thing.py:1: 1;")
              and f"This task's command: {job.survivor_task_recorded_mutant_killed_check_command_line([line_one_diff_file])}\n"
                  in task_six["description"]
              and line_one_diff_file.is_file() and task_six["status"] == "pending"
              and "SURVIVED scripts/thing.py:3 core/ReplaceUnaryOperator_Delete_Not: task #10 opened" in record
              and fixture.state_json()["tasks_opened"].get(job.mutant_key(line_one))
              == {"agent_seat": "alpha", "task_id": 6},
              (record, task_six, fixture.state_json()))
        later = fixture.commit("scripts/other.py", "VALUE = 2\n", author="alpha")
        new_on_line_two = survivor(2, "core/ReplaceComparisonOperator")
        completed = fixture.run({later: {"json": verdict(survived=[survivor(), new_on_line_two])}})
        record = fixture.records()[-1].read_text()
        task_nine = json.loads((alpha_list / "9.json").read_text())
        new_diff_file = job.mutant_diff_file_path(fixture.log_store, job.mutant_key(new_on_line_two))
        check("a later merge's survivors on a line whose task is still open get no second task: "
              "one the state names is already given it, and a new one is added to it, the task "
              "rewritten with one command for all four, and named in the state, so it stays "
              "reported",
              completed.returncode == 0
              and task_files(alpha_list) == ["10.json", "6.json", "7.json", "8.json", "9.json"]
              and "SURVIVED scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Mul: already given "
                  "task #9 on alpha's task list" in record
              and "SURVIVED scripts/thing.py:2 core/ReplaceComparisonOperator: added to task #9"
                  in record
              and task_nine["subject"].startswith("Surviving mutants in scripts/thing.py:2: 4;")
              and f"This task's command: "
                  f"{job.survivor_task_recorded_mutant_killed_check_command_line(sorted([*diff_files, new_diff_file]))}\n"
                  in task_nine["description"]
              and fixture.state_json()["tasks_opened"].get(job.mutant_key(new_on_line_two))
              == {"agent_seat": "alpha", "task_id": 9},
              (completed.returncode, completed.stderr, task_files(alpha_list), record, task_nine))
        completed = fixture.run({})
        check("a run after the addition finds task #9 still holding the added survivor",
              completed.returncode == 0 and "TASK LOST" not in fixture.records()[-1].read_text(),
              (completed.returncode, completed.stderr))
        task = task_nine
        task["status"] = "completed"
        (alpha_list / "9.json").write_text(json.dumps(task))
        last = fixture.commit("scripts/other.py", "VALUE = 3\n", author="alpha")
        completed = fixture.run({last: {"json": verdict(survived=[new_on_line_two])}})
        check("once the line's task is completed, a survivor on the line gets a new task",
              completed.returncode == 0 and "11.json" in task_files(alpha_list)
              and fixture.state_json()["tasks_opened"].get(job.mutant_key(new_on_line_two))
              == {"agent_seat": "alpha", "task_id": 11},
              (completed.returncode, completed.stderr, task_files(alpha_list)))

    # A survivor on a line whose task is open, when that task cannot be rewritten: the run stops
    # at the merge before the state names the task for it, and the task is left as it was.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        completed = fixture.run({merge: {"json": verdict(survived=[survivor()])}})
        before = (alpha_list / "1.json").read_text()
        later = fixture.commit("scripts/other.py", "VALUE = 2\n", author="alpha")
        added = survivor(2, "core/ReplaceComparisonOperator")
        (alpha_list / ".1.json.partial").mkdir()
        completed = fixture.run({later: {"json": verdict(survived=[added])}})
        check("a survivor on a line whose open task cannot be rewritten stops the run at that "
              "merge, exit 4, naming the error, with the task unchanged, the merge not recorded "
              "as tested and the state not naming the task for the survivor",
              completed.returncode == job.EXIT_STEP_FAILED
              and f"merge {later[:12]}: no task could be opened on alpha's task list, or "
                  f"rewritten there" in completed.stderr
              and "IsADirectoryError" in completed.stderr
              and (alpha_list / "1.json").read_text() == before
              and fixture.state_json()["last_tested_main_commit"] == merge
              and job.mutant_key(added) not in fixture.state_json()["tasks_opened"],
              (completed.returncode, completed.stderr, fixture.state_json()))

    # The recheck: each night, each survivor task the state names is judged on main by the
    # recorded mutant killed check; killed mutants and mutants that no longer exist leave the
    # task and the state, and a task with none left is completed.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        mutants = [survivor(), survivor(2, "core/ReplaceBinaryOperator_Add_Sub"),
                   dict(survivor(2, "core/ReplaceBinaryOperator_Add_Div"),
                        diff=SURVIVOR_DIFF.replace("x * x", "x / x"))]
        keys = [job.mutant_key(mutant) for mutant in mutants]
        diff_files = [job.mutant_diff_file_path(fixture.log_store, key) for key in keys]
        completed = fixture.run({merge: {"json": verdict(survived=mutants)}})
        main_commit = git(fixture.work, "rev-parse", "HEAD")
        calls_before = len(fixture.calls())
        completed = fixture.run({"recheck": {"verdicts": {
            keys[0]: "killed", keys[1]: "no longer exists", keys[2]: "survived"}}})
        recheck_call = fixture.calls()[calls_before] if len(fixture.calls()) > calls_before else []
        task = json.loads((alpha_list / "1.json").read_text())
        record = fixture.records()[-1].read_text()
        check("the recheck runs the recorded mutant killed check on main with every diff file "
              "of the task, and asks for its verdicts as JSON",
              recheck_call[:1] == ["--recorded-mutant-killed-check"]
              and sorted(recheck_call[1:4]) == sorted(map(str, diff_files))
              and recheck_call[recheck_call.index("--head") + 1] == main_commit
              and "--recorded-mutant-killed-check-verdicts-json-file-to-write" in recheck_call,
              recheck_call)
        check("a killed mutant and one that no longer exists leave the task and the state; the "
              "task is rewritten to list only the survivor, with its count, and stays pending",
              completed.returncode == 0
              and task["subject"].startswith("Surviving mutants in scripts/thing.py:2: 1;")
              and task["status"] == "pending"
              and f"This task's command: {job.survivor_task_recorded_mutant_killed_check_command_line([diff_files[2]])}\n"
                  in task["description"]
              and str(diff_files[0]) not in task["description"]
              and str(diff_files[1]) not in task["description"]
              and task["description"].endswith(
                  job.SURVIVOR_TASK_DESCRIPTION_LAST_LINE_LEAVE_TASK_OPEN_FOR_NIGHTLY_RECHECK)
              and list(fixture.state_json()["tasks_opened"]) == [keys[2]]
              and "RECHECKED task #1 on alpha's task list: 1 killed, 1 no longer exists, "
                  "1 survived, 0 could not be judged; rewritten to list only the surviving "
                  "mutants" in record,
              (completed.returncode, completed.stderr, task, fixture.state_json(), record))
        completed = fixture.run({"recheck": {"verdicts": {keys[2]: "could not be judged"}}})
        check("a recheck that leaves the task's mutants as they were leaves the task file "
              "unchanged, and a mutant that could not be judged stays listed",
              completed.returncode == 0
              and json.loads((alpha_list / "1.json").read_text()) == task
              and list(fixture.state_json()["tasks_opened"]) == [keys[2]]
              and "1 could not be judged; unchanged" in fixture.records()[-1].read_text(),
              (completed.returncode, completed.stderr))
        completed = fixture.run({"recheck": {"verdicts": {keys[2]: "killed"}}})
        task = json.loads((alpha_list / "1.json").read_text())
        check("once no mutant of a task survives on main, the task is completed, saying why, and "
              "the state names none of its mutants",
              completed.returncode == 0 and task["status"] == "completed"
              and "Completed by the scheduled full mutation pass: on main at "
                  f"{main_commit[:12]}, every mutant this task listed is killed or no longer "
                  f"exists." in task["description"]
              and fixture.state_json()["tasks_opened"] == {}
              and "; completed" in fixture.records()[-1].read_text(),
              (completed.returncode, completed.stderr, task, fixture.state_json()))
        calls_before = len(fixture.calls())
        completed = fixture.run()
        check("a completed task is not rechecked again, and nothing is reported lost",
              completed.returncode == 0 and len(fixture.calls()) == calls_before
              and "TASK LOST" not in fixture.records()[-1].read_text(),
              (completed.returncode, completed.stderr))

    # A task an earlier version opened, with its subject and its last line telling the agent to
    # mark it completed, is rewritten by the first recheck, its status kept.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        key = job.mutant_key(survivor())
        diff_file = job.mutant_diff_file_path(fixture.log_store, key)
        diff_file.parent.mkdir(parents=True)
        diff_file.write_text(SURVIVOR_DIFF)
        (alpha_list / "4.json").write_text(json.dumps({
            "id": "4", "status": "in_progress", "blocks": [], "blockedBy": [],
            "subject": "Surviving mutant in scripts/thing.py:2: add a test that kills it, or "
                       "record why no test can",
            "description": f"Its command: python3 scripts/{job.MUTATION_TESTING_PROGRAM.name} "
                           f"--recorded-mutant-killed-check {diff_file}\nOnce you have opened a "
                           f"pull request for this task, mark this task completed."}))
        state = fixture.state_json()
        state["tasks_opened"] = {key: {"agent_seat": "alpha", "task_id": 4}}
        (fixture.state / job.STATE_FILE_NAME).write_text(json.dumps(state))
        completed = fixture.run({"recheck": {}})
        task = json.loads((alpha_list / "4.json").read_text())
        check("a task an earlier version opened, still surviving, is rewritten to this version's "
              "subject, command and last line, with its status kept",
              completed.returncode == 0 and task["status"] == "in_progress"
              and task["subject"].startswith("Surviving mutants in scripts/thing.py:2: 1;")
              and f"This task's command: {job.survivor_task_recorded_mutant_killed_check_command_line([diff_file])}\n"
                  in task["description"]
              and "mark this task completed" not in task["description"]
              and task["description"].endswith(
                  job.SURVIVOR_TASK_DESCRIPTION_LAST_LINE_LEAVE_TASK_OPEN_FOR_NIGHTLY_RECHECK)
              and "+    return x * x" in task["description"],
              (completed.returncode, completed.stderr, task))

    # A recheck that gives no verdicts leaves its task as it was and the merges are still tested;
    # one that runs past its limit is stopped; a task the recheck cannot rewrite stops the run.
    for case_name, plan_step, flags, wanted in [
        ("the recorded mutant killed check writes no verdicts", {"no_verdicts": True, "exit": 2,
                                                                  "stdout": "could not run"},
         (), "the recorded mutant killed check exited 2 without verdicts (FileNotFoundError: "),
        ("with nothing on standard error, the recorded mutant killed check's last line of "
         "standard output is named", {"no_verdicts": True, "exit": 2,
                                      "stdout": "checking\ncould not run"},
         (), "; it printed:\n    could not run\n"),
        ("the recorded mutant killed check's whole standard error is named",
         {"no_verdicts": True, "exit": 2, "stdout": "checking",
          "stderr": "mutation-testing: git worktree add failed (exit 128): Preparing worktree\n"
                    "error: unable to write file README: No space left on device\n"
                    "fatal: Could not reset index file to revision 'HEAD'."},
         (), "; it printed:\n    mutation-testing: git worktree add failed (exit 128): "
             "Preparing worktree\n    error: unable to write file README: No space left on "
             "device\n    fatal: Could not reset index file to revision 'HEAD'.\n"),
        ("the recorded mutant killed check runs past its limit", {"sleep": 30}, (
            "--survivor-task-recorded-mutant-killed-check-timeout-seconds", "1"),
         "the recorded mutant killed check ran past the limit of 1 s without verdicts"),
    ]:
        with tempfile.TemporaryDirectory() as scratch:
            fixture = Fixture(scratch)
            alpha_list = fixture.seat("alpha")
            fixture.seat(job.JOB_FAILURE_TASK_AGENT_SEAT)
            fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
            merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                                   author="alpha")
            fixture.run({merge: {"json": verdict(
                survived=[survivor(1, "core/NumberReplacer"), survivor()])}})
            before = (alpha_list / "1.json").read_text()
            state_before = fixture.state_json()["tasks_opened"]
            later = fixture.commit("scripts/other.py", "VALUE = 2\n", author="alpha")
            completed = fixture.run({"recheck": {**plan_step, "verdicts": {
                job.mutant_key(survivor()): "killed"}}, later: {"json": verdict()}}, *flags)
            record = fixture.records()[-1].read_text()
            opened = [task for task in job_failure_tasks(fixture) if task["subject"]
                      == job.SURVIVOR_TASKS_NOT_RECHECKED_TASK_SUBJECT]
            check(f"{case_name}: each of two tasks and the state are left as they were, the "
                  f"record, standard error and one job failure task name both tasks, the merges "
                  f"are still tested, and the run exits 8",
                  len(opened) == 1
                  and "task #1 on alpha's task list" in opened[0]["description"]
                  and "task #2 on alpha's task list" in opened[0]["description"]
                  and f"JOB FAILURE TASK: opened task #{opened[0]['id']}" in record
                  and
                  completed.returncode
                  == job.EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS
                  and (alpha_list / "1.json").read_text() == before
                  and fixture.state_json()["tasks_opened"] == state_before
                  and fixture.state_json()["last_tested_main_commit"] == later
                  and "NOT RECHECKED: task #1 on alpha's task list" in record
                  and "NOT RECHECKED: task #2 on alpha's task list" in record
                  and wanted in completed.stderr
                  and "2 survivor task(s) were left as they were" in completed.stderr,
                  (completed.returncode, completed.stderr, fixture.records()[-1].read_text()))

    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        alpha_list = fixture.seat("alpha")
        fixture.set_last(git(fixture.work, "rev-parse", "HEAD"))
        merge = fixture.commit("scripts/thing.py", "def double(x):\n    return x + x\n",
                               author="alpha")
        mutants = [survivor(), survivor(2, "core/ReplaceBinaryOperator_Add_Sub")]
        fixture.run({merge: {"json": verdict(survived=mutants)}})
        before = (alpha_list / "1.json").read_text()
        state_before = fixture.state_json()
        (alpha_list / ".1.json.partial").mkdir()
        later = fixture.commit("scripts/other.py", "VALUE = 2\n", author="alpha")
        calls_before = len(fixture.calls())
        completed = fixture.run({"recheck": {"verdicts": {
            job.mutant_key(mutants[0]): "killed"}}, later: {"json": verdict()}})
        check("a task the recheck cannot rewrite stops the run, exit 4, naming the task and the "
              "error, with the task and the state as they were and no merge tested",
              completed.returncode == job.EXIT_STEP_FAILED
              and "task #1 on alpha's task list" in completed.stderr
              and "was rechecked on main (1 killed, 0 no longer exists, 1 survived, 0 could not "
                  "be judged), but a file could not be read or written (IsADirectoryError"
                  in completed.stderr
              and (alpha_list / "1.json").read_text() == before
              and fixture.state_json() == state_before
              and len(fixture.calls()) == calls_before + 1,
              (completed.returncode, completed.stderr, fixture.state_json()))

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
              and "Set last_tested_main_commit" in completed.stderr
              and "the next run tests the merges after it" in completed.stderr, completed.stderr)

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
              and "git fetch --quiet origin main failed" in fixture.records()[0].read_text()
              and "does not appear to be a git repository" in fixture.records()[0].read_text()
              and "Could not read from remote repository" in fixture.records()[0].read_text(),
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

    # The hand run a job failure task gives holds the job's lock, because it shares the
    # merge's kept sessions with the nightly run.
    if not FLOCK_PROGRAM.exists():
        # The job runs only on ned-box; the Mac's scheduled full test run still runs this suite.
        print(f"SKIP  [this machine cannot run it] the hand-run command's lock case: {FLOCK_PROGRAM} is missing; it exists on Linux only")
    else:
        with tempfile.TemporaryDirectory() as scratch:
            scratch = Path(scratch)
            state = scratch / "state directory"
            state.mkdir()
            ran = scratch / "ran"
            program = scratch / "fake-program.py"
            program.write_text("import sys, time\nfrom pathlib import Path\n"
                               f"Path({str(ran)!r}).write_text('ran')\ntime.sleep(3)\n")
            arguments = type("Arguments", (), {
                "log_store_root": str(scratch / "logs"), "state_directory": state,
                "mutation_testing_program": str(program), "clone": scratch / "clone",
                "cosmic_ray_venv": scratch / "venv"})()
            command = job.mutation_testing_hand_run_command(arguments, "a" * 40, "b" * 40, 2,
                                                            scratch / "sessions")
            # What systemd-run runs: the command after its own options.
            under_lock = command[command.index("/usr/bin/flock "):]
            with open(state / job.LOCK_FILE_NAME, "a") as holder:
                fcntl.flock(holder, fcntl.LOCK_EX)
                hand_run = subprocess.Popen(["sh", "-c", under_lock])
                time.sleep(2)
                ran_while_held = ran.exists()
            deadline = time.monotonic() + 30
            while not ran.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            nightly_lock = job.take_lock(state / job.LOCK_FILE_NAME)
            hand_run_exit = hand_run.wait(timeout=60)
            check("a hand run waits while a run holds the job's lock, then runs the mutation "
                  "testing program, and the nightly run cannot take the lock while it runs",
                  not ran_while_held and ran.exists() and nightly_lock is None
                  and hand_run_exit == 0,
                  f"ran_while_held={ran_while_held} ran={ran.exists()} "
                  f"nightly_lock={nightly_lock} exit={hand_run_exit}")
            if nightly_lock is not None:
                nightly_lock.close()

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

    run_every_exit_but_0_6_7_9_opens_a_job_failure_task_cases()

    # A state file that cannot be opened at all.
    with tempfile.TemporaryDirectory() as scratch:
        fixture = Fixture(scratch)
        (fixture.state / job.STATE_FILE_NAME).mkdir(parents=True)
        completed = fixture.run()
        check("a state file that cannot be opened: exit 4, and the record names the error",
              completed.returncode == job.EXIT_STEP_FAILED
              and "FAILED: [Errno 21] Is a directory" in fixture.records()[0].read_text(),
              f"rc={completed.returncode} err={completed.stderr}")

    # A mutation testing program that ignores SIGTERM at the limit is killed. It would sleep
    # an hour, so without the kill run_mutation_testing() would not return within the bound; the
    # program writes its pid so the test can kill it itself then, instead of hanging.
    with tempfile.TemporaryDirectory() as scratch:
        program = Path(scratch) / "ignores-sigterm.py"
        pid_file = Path(scratch) / "pid"
        program.write_text("import os, signal, sys, time\n"
                           "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                           f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
                           "print('still going', flush=True)\ntime.sleep(3600)\n")
        arguments = job.parse_arguments(["--mutation-testing-program", str(program),
                                         "--merge-timeout-seconds", "1"])
        cleanup_seconds = job.SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM
        job.SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM = 1
        result = []
        runner = threading.Thread(target=lambda: result.append(job.run_mutation_testing(
            arguments, "a" * 40, "b" * 40, Path(scratch) / "out.json", 1,
            Path(scratch) / "sessions")), daemon=True)
        try:
            runner.start()
            runner.join(timeout=60)
        finally:
            job.SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM = cleanup_seconds
        returned_within_bound = not runner.is_alive()
        if not returned_within_bound and pid_file.exists():
            os.kill(int(pid_file.read_text()), signal.SIGKILL)
            runner.join(timeout=30)
        exit_code, stdout, _ = result[0] if result else ("no result", "", "")
        check("a mutation testing program still running after SIGTERM and the time to clean up "
              "is killed, and reported as past the limit with its output kept",
              returned_within_bound and exit_code is None and "still going" in stdout,
              (returned_within_bound, exit_code, stdout))

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
