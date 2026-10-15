#!/usr/bin/env python3
"""Two real test runs on one machine at once: neither waits for the other, and neither disturbs the other.

Runs scripts/run-all-test-suites.py, and scripts/run-suite-in-signal-sandbox.py,
as real processes, each suite in its own test sandbox. Admission's CPU and
memory thresholds are opened wide by a small driver, so the cases do not
depend on how busy the machine is; the admission directory is this test's own.

The last case is the collision that made test runs take turns: two
overlapping runs of scripts/resupervise-seat-test.py both exited 0 while
silently dropping cases to SKIP, because they shared tmux sockets under /tmp.

Linux with bwrap only; elsewhere every case is skipped. It starts bwrap, which
cannot start inside bwrap, so the runner runs it outside the test sandbox.

Run: python3 scripts/run-all-test-suites-overlapping-runs-real-process-test.py   (exit 0 = all passed)
"""

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

# Before anything runs git, so the scratch repository is built where this suite says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
CHECKOUT = SCRIPTS_DIR.parent
RUNNER_PATH = SCRIPTS_DIR / "run-all-test-suites.py"
ONE_SUITE_PATH = SCRIPTS_DIR / "run-suite-in-signal-sandbox.py"

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail!r}"[:1500])


# Loads a program as a module, opens admission's thresholds wide, and runs its main.
DRIVER_SOURCE = r'''
import importlib.util, sys
program_path, *arguments = sys.argv[1:]
spec = importlib.util.spec_from_file_location("program_under_test", program_path)
program = importlib.util.module_from_spec(spec)
sys.argv = [program_path, *arguments]
spec.loader.exec_module(program)
runner = getattr(program, "runner", program)
runner.TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW = 101
runner.TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE = -1
sys.exit(program.main(arguments))
'''

# Each suite claims one fixed name under /tmp and holds it: two suites sharing /tmp
# would find each other's claim.
CLAIMING_SUITE = r'''
import os, time
claim = "/tmp/run-all-test-suites-overlapping-runs-claim"
if os.path.exists(claim):
    print(f"FAIL  the claim under /tmp is free: another suite holds it: {open(claim).read()}")
    raise SystemExit(1)
with open(claim, "w") as handle:
    handle.write(str(os.getpid()))
print("PASS  claimed /tmp alone", flush=True)
print(f"PASS  runs at niceness {os.nice(0)}", flush=True)
time.sleep(3)
print("PASS  still alone after 3 s", flush=True)
'''


def unavailable_because():
    if not sys.platform.startswith("linux"):
        return f"{sys.platform} has no test sandbox"
    if shutil.which("bwrap") is None:
        return "bwrap is not on PATH"
    return None


def run_together(commands, cwd):
    processes = [subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                 for command in commands]
    outputs = []
    for process in processes:
        try:
            output, _ = process.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
            output += "\n(timed out)"
        outputs.append((process.returncode, output))
    return outputs


def case_rows(log_dir):
    rows = (log_dir / "test-case-times.tsv").read_text().splitlines()[1:]
    return [row.split("\t") for row in rows]


why = unavailable_because()
if why is not None:
    print(f"SKIP  every case: {why}")
    sys.exit(0)

with tempfile.TemporaryDirectory(prefix="run-all-test-suites-overlapping-runs-") as scratch_name:
    scratch = pathlib.Path(scratch_name)
    repository = scratch / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    (repository / "claims-tmp-test.py").write_text(CLAIMING_SUITE)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "-m", "start"], cwd=repository, check=True)
    lock_file = scratch / "machine" / "run.lock"

    runs = run_together(
        [[sys.executable, "-c", DRIVER_SOURCE, str(RUNNER_PATH), "--checkout", str(repository),
          "--lock-file", str(lock_file), "--log-dir", str(scratch / f"logs-{name}"),
          "--recorded-inputs-directory", str(scratch / f"recorded-{name}"),
          "--wait-for-lock-seconds", "1"]
         for name in ("first", "second")], scratch)
    check("two runs started together both pass, each suite alone in its own /tmp",
          all(code == 0 for code, _ in runs), runs)
    check("neither run waited for a machine lock",
          not any("waiting up to" in output or "seconds waiting for the machine's lock" in output
                  for _, output in runs), runs)
    first_rows = case_rows(scratch / "logs-first")
    second_rows = case_rows(scratch / "logs-second")
    first_times = [float(row[4]) for row in first_rows]
    second_times = [float(row[4]) for row in second_rows]
    check("the runs overlapped: each run's suite printed a case while the other's suite ran",
          len(first_times) == 3 and len(second_times) == 3
          and first_times[0] < second_times[-1] and second_times[0] < first_times[-1],
          (first_rows, second_rows))
    for name in ("first", "second"):
        log_dir = scratch / f"logs-{name}"
        resources = (log_dir / "test-suite-resource-use.tsv").read_text().splitlines()
        fields = resources[1].split("\t") if len(resources) > 1 else []
        check(f"the {name} run records the suite's kind, admission wait, CPU seconds and peak "
              f"memory", len(fields) == 8 and fields[1] == "test sandbox"
              and fields[4] != "" and fields[5] != "" and int(fields[6] or 0) > 0, resources)
        readings = (log_dir / "machine-cpu-and-memory-readings.tsv").read_text().splitlines()
        check(f"the {name} run records the machine's readings each second", len(readings) >= 3,
              readings)
        check(f"the {name} run records each case's time, and writes JUnit XML",
              len(case_rows(log_dir)) == 3 and (log_dir / "junit.xml").is_file())
        # Niceness stops at 19, and this test itself runs at nice 10 under the runner.
        expected_niceness = min(os.nice(0) + 10, 19)
        check(f"the {name} run's suite runs at low priority, niceness "
              f"{expected_niceness} where this test runs at {os.nice(0)}",
              any(row[5] == f"runs at niceness {expected_niceness}"
                  for row in case_rows(log_dir)), case_rows(log_dir))
        report = (log_dir / "report.txt").read_text()
        check(f"the {name} run reports how long its suites waited for admission",
              "seconds suites waited for admission: " in report, report[-800:])

    # Admission that cannot work stops the run with exit 2, saying why.
    blocked = scratch / "blocked"
    blocked.mkdir()
    (blocked / "run.lock.test-suite-admission").write_text("a file where the admission "
                                                          "directory belongs\n")
    code, output = run_together(
        [[sys.executable, "-c", DRIVER_SOURCE, str(RUNNER_PATH), "--checkout", str(repository),
          "--lock-file", str(blocked / "run.lock"), "--log-dir", str(scratch / "logs-blocked"),
          "--recorded-inputs-directory", str(scratch / "recorded-blocked")]], scratch)[0]
    check("an admission directory that cannot be made stops the run with exit 2, saying so",
          code == 2 and "admission could not start" in output, (code, output[-800:]))
    unopenable = scratch / "unopenable"
    (unopenable / "run.lock.test-suite-admission" / "slot-00").mkdir(parents=True)
    code, output = run_together(
        [[sys.executable, "-c", DRIVER_SOURCE, str(RUNNER_PATH), "--checkout", str(repository),
          "--lock-file", str(unopenable / "run.lock"),
          "--log-dir", str(scratch / "logs-unopenable"),
          "--recorded-inputs-directory", str(scratch / "recorded-unopenable")]], scratch)[0]
    check("a slot file that cannot be opened stops the run with exit 2, naming the file",
          code == 2 and "admission failed" in output and "slot-00" in output,
          (code, output[-800:]))

    # The collision that made test runs take turns, on the real suite.
    collisions = run_together(
        [[sys.executable, "-c", DRIVER_SOURCE, str(ONE_SUITE_PATH),
          "scripts/resupervise-seat-test.py", "--checkout", str(CHECKOUT),
          "--lock-file", str(lock_file)] for _ in range(2)], CHECKOUT)
    check("two runs of scripts/resupervise-seat-test.py at once both pass",
          all(code == 0 and "VERDICT: suite passed" in output for code, output in collisions),
          collisions)
    check("neither run of scripts/resupervise-seat-test.py waited for a machine lock",
          not any("waiting up to" in output for _, output in collisions), collisions)
    check("neither run of scripts/resupervise-seat-test.py dropped a case to SKIP",
          not any(line.startswith("SKIP") for _, output in collisions
                  for line in output.splitlines()),
          [line for _, output in collisions for line in output.splitlines()
           if line.startswith("SKIP")])

print(f"{len(failures)} failed" if failures else "all cases passed")
sys.exit(1 if failures else 0)
