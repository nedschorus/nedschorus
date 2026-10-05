#!/usr/bin/env python3
"""Two copies of main-gatekeeper-test.py run at once give the same case results as one run alone.

Run: python3 nc-systems/main-gatekeeper/tests/main-gatekeeper-suite-paired-overlap-test.py

The suite is run once alone, then twice at the same time. Both copies are
held at a barrier in front of the pid-1 cancel case, so its cancels overlap
rather than merely starting together. Each copy must report the same case
names, the same PASS, FAIL and SKIP verdicts, the same case count and the
same exit code as the run alone. A control feeds the comparison a result
with one case removed and one verdict flipped, and expects it to be caught.
Each copy writes to a file of its own; a stand-in case checks that a copy
printing more than a pipe holds before the barrier does not stall the other.

Prints one line per case and exits non-zero if any case fails.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SUITE_PATH = Path(__file__).resolve().parent / "main-gatekeeper-test.py"
SUITE_TIMEOUT_SECONDS = 900
PID_ONE_CASE = "cancel sends no signal toward pid 1 or a group at or below 1"

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def suite_environment(barrier_directory=None, participants=0):
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    environment.pop("MAIN_GATEKEEPER_TEST_PAIRED_OVERLAP_BARRIER_DIRECTORY", None)
    environment.pop("MAIN_GATEKEEPER_TEST_PAIRED_OVERLAP_PARTICIPANTS", None)
    if barrier_directory is not None:
        environment["MAIN_GATEKEEPER_TEST_PAIRED_OVERLAP_BARRIER_DIRECTORY"] = str(barrier_directory)
        environment["MAIN_GATEKEEPER_TEST_PAIRED_OVERLAP_PARTICIPANTS"] = str(participants)
    return environment


def start_suite(environment, output_path, command=None):
    """Start a copy writing to a file of its own.

    A pipe read only after the other copy finishes fills up: a copy that writes
    more than the pipe holds before the barrier then blocks, and the other
    copy waits at the barrier for it until the deadline.
    """
    output_file = open(output_path, "w", encoding="utf-8")
    try:
        process = subprocess.Popen(command or [sys.executable, "-B", "-u", str(SUITE_PATH)],
                                   stdout=output_file, stderr=subprocess.STDOUT,
                                   text=True, env=environment)
    finally:
        output_file.close()
    return process, Path(output_path)


def finish_suite(started, timeout=SUITE_TIMEOUT_SECONDS):
    process, output_path = started
    try:
        process.wait(timeout=timeout)
        exit_status = process.returncode
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        exit_status = "timed out"
    return {"exit": exit_status,
            "output": output_path.read_text(encoding="utf-8", errors="replace")}


def case_results(output):
    """The suite's verdict for each case name, and the case count it printed."""
    verdicts = []
    for line in output.splitlines():
        match = re.match(r"^(PASS|FAIL|SKIP)  (.*)$", line)
        if match:
            verdict, rest = match.groups()
            name = rest.split(": ", 1)[0] if verdict != "PASS" else rest
            verdicts.append((name, verdict))
    count = re.search(r"^(\d+) cases run$", output, re.MULTILINE)
    return sorted(verdicts), int(count.group(1)) if count else None


def differences(alone, copy):
    """Every way a copy's results differ from the run alone; empty when they match."""
    alone_verdicts, alone_count = case_results(alone["output"])
    copy_verdicts, copy_count = case_results(copy["output"])
    found = []
    if copy_verdicts != alone_verdicts:
        found.append(("verdicts", sorted(set(alone_verdicts) ^ set(copy_verdicts))))
    if copy_count != alone_count:
        found.append(("case count", alone_count, copy_count))
    if copy["exit"] != alone["exit"]:
        found.append(("exit", alone["exit"], copy["exit"]))
    return found


# Stand-ins for the two copies: the second writes far more than a pipe holds
# before it arrives, and the first waits for that arrival, as a failing case's
# diagnostics before the barrier would make the real copies do.
WAITING_COPY = """
import pathlib, sys, time
marker = pathlib.Path(sys.argv[1])
deadline = time.monotonic() + 20
while not marker.exists():
    if time.monotonic() > deadline:
        print("the other copy never arrived")
        sys.exit(1)
    time.sleep(0.05)
print("arrived together")
"""
WRITING_COPY = """
import pathlib, sys
sys.stdout.write("x" * (1024 * 1024) + "\\n")
sys.stdout.flush()
pathlib.Path(sys.argv[1]).touch()
"""

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = Path(scratch_name)
    marker = scratch / "writing-copy-arrived"
    stand_ins = [
        start_suite(suite_environment(), scratch / "waiting.out",
                    [sys.executable, "-c", WAITING_COPY, str(marker)]),
        start_suite(suite_environment(), scratch / "writing.out",
                    [sys.executable, "-c", WRITING_COPY, str(marker)]),
    ]
    stand_in_results = [finish_suite(started, timeout=60) for started in stand_ins]
    check("a copy that prints more than a pipe holds before the barrier does not hold up the other copy",
          [result["exit"] for result in stand_in_results] == [0, 0]
          and len(stand_in_results[1]["output"]) > 1024 * 1024,
          [(result["exit"], result["output"][:200]) for result in stand_in_results])

    alone = finish_suite(start_suite(suite_environment(), scratch / "alone.out"))
    alone_verdicts, alone_count = case_results(alone["output"])
    check("the run alone reaches the pid-1 cancel case",
          (PID_ONE_CASE, "PASS") in alone_verdicts, alone["output"][-2000:])
    check("the run alone prints its case count", alone_count is not None,
          alone["output"][-2000:])

    barrier = scratch / "barrier"
    barrier.mkdir()
    environment = suite_environment(barrier, participants=2)
    copies = [start_suite(environment, scratch / f"copy-{number}.out") for number in (1, 2)]
    results = [finish_suite(copy) for copy in copies]
    arrived = sorted(path.name for path in barrier.glob("arrived-*"))
    check("both copies reached the barrier in front of the pid-1 cancel case",
          len(arrived) == 2, arrived)

for number, result in enumerate(results, start=1):
    check(f"copy {number} run alongside the other gives the same results as the run alone",
          not differences(alone, result),
          (differences(alone, result), result["output"][-2000:]))

# Control: a comparison that cannot see a dropped case or a flipped verdict would
# pass the cases above whatever the copies printed.
dropped = {**alone, "output": alone["output"].replace(f"PASS  {PID_ONE_CASE}\n", "", 1)}
flipped = {**alone, "output": alone["output"].replace(
    f"PASS  {PID_ONE_CASE}\n", f"FAIL  {PID_ONE_CASE}: control\n", 1)}
check("control: the comparison catches a copy missing one case",
      bool(differences(alone, dropped)), differences(alone, dropped))
check("control: the comparison catches a copy with one verdict flipped",
      bool(differences(alone, flipped)), differences(alone, flipped))

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
