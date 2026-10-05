#!/usr/bin/env python3
"""Two copies of main-gatekeeper-test.py run at once give the same case results as one run alone.

Run: python3 nc-systems/main-gatekeeper/tests/main-gatekeeper-suite-paired-overlap-test.py

The suite is run once alone, then twice at the same time. Both copies are
held at a barrier in front of the pid-1 cancel case, so its cancels overlap
rather than merely starting together. Each copy must report the same case
names, the same PASS, FAIL and SKIP verdicts, the same case count and the
same exit code as the run alone. A control feeds the comparison a result
with one case removed and one verdict flipped, and expects it to be caught.

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


def start_suite(environment):
    return subprocess.Popen([sys.executable, "-B", "-u", str(SUITE_PATH)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=environment)


def finish_suite(process):
    try:
        output, _ = process.communicate(timeout=SUITE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        return {"exit": "timed out", "output": output}
    return {"exit": process.returncode, "output": output}


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


alone = finish_suite(start_suite(suite_environment()))
alone_verdicts, alone_count = case_results(alone["output"])
check("the run alone reaches the pid-1 cancel case",
      (PID_ONE_CASE, "PASS") in alone_verdicts, alone["output"][-2000:])
check("the run alone prints its case count", alone_count is not None,
      alone["output"][-2000:])

with tempfile.TemporaryDirectory() as barrier_name:
    barrier = Path(barrier_name)
    environment = suite_environment(barrier, participants=2)
    copies = [start_suite(environment), start_suite(environment)]
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
