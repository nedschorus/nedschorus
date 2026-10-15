#!/usr/bin/env python3
"""Tests for the admission, machine readings and run records of scripts/run-all-test-suites.py.

Admission is tested with stubbed readings, clocks and sleeps, in an admission
directory of this test's own, so no case depends on how busy the machine is.

Run: python3 scripts/run-all-test-suites-machine-wide-test-suite-admission-test.py   (exit 0 = all passed)
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree

# Before anything runs git, so the scratch repository is built where this suite says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
RUNNER_PATH = SCRIPTS_DIR / "run-all-test-suites.py"

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail!r}"[:1200])


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("run_all_test_suites", RUNNER_PATH)
GB = 10**9


class Readings:
    def __init__(self, cpu=10.0, available=40 * GB):
        self.cpu, self.available = cpu, available

    def cpu_percent_average(self):
        return self.cpu

    def available_memory_bytes(self):
        return self.available


class Clock:
    """A clock and a sleep that move together, so a waiting suite never really sleeps."""

    def __init__(self):
        self.now = 1000.0
        self.on_sleep = None

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        if self.on_sleep is not None:
            self.on_sleep()


def admission_in(directory, readings, said=None, clock=None):
    clock = clock or Clock()
    return runner.MachineWideTestSuiteAdmission(
        directory, readings, (said if said is not None else []).append,
        clock=clock.clock, sleep=clock.sleep, machine_clock=clock.clock), clock


def free_starts(directory):
    """Forget earlier starts, so a case is not held back by the per-second limit."""
    (pathlib.Path(directory) / runner.TEST_SUITE_ADMISSION_START_TIMES_FILE_NAME).unlink(
        missing_ok=True)


with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)

    # --- The thresholds -------------------------------------------------------
    for cpu, available, admitted_expected, label in (
            (49.9, 10 * GB + 1, True, "CPU just under 50% and memory just above 10 GB"),
            (50.0, 40 * GB, False, "CPU at 50%"),
            (80.0, 40 * GB, False, "CPU above 50%"),
            (10.0, 10 * GB, False, "available memory at 10 GB"),
            (10.0, 2 * GB, False, "available memory below 10 GB")):
        directory = scratch / f"thresholds-{cpu}-{available}"
        readings = Readings(cpu, available)
        said = []
        admission, clock = admission_in(directory, readings, said)
        started = threading.Event()

        def give_room(readings=readings):
            readings.cpu, readings.available = 10.0, 40 * GB

        clock.on_sleep = give_room
        with admission.admitted("a-test.py") as waited:
            started.set()
        check(f"admission {'starts' if admitted_expected else 'holds back'} a suite at {label}",
              (waited == 0) == admitted_expected, (waited, said))
        if not admitted_expected:
            check(f"the run says what its suite waits for at {label}",
                  said and ("CPU" in said[0] if cpu >= 50 else "memory" in said[0]), said)

    # --- The ceiling of suites at once --------------------------------------
    directory = scratch / "ceiling"
    admission, clock = admission_in(directory, Readings())
    held = contextlib.ExitStack()
    ceiling = runner.TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING
    for number in range(ceiling):
        free_starts(directory)
        held.enter_context(admission.admitted(f"suite-{number}-test.py"))
    free_starts(directory)
    slot, why = admission.take_a_start_and_a_slot()
    check(f"with {ceiling} suites running, no further suite is admitted, and the reason "
          f"names the ceiling", slot is None and str(ceiling) in (why or ""), why)
    other_run, _ = admission_in(directory, Readings())
    slot, why = other_run.take_a_start_and_a_slot()
    check("another run sharing the admission directory is held back by the same ceiling",
          slot is None, why)
    held.close()
    free_starts(directory)
    slot, why = admission.take_a_start_and_a_slot()
    check("once the suites end, their slots are free again", slot is not None, why)
    if slot is not None:
        slot.close()

    # A slot held by a process that is killed is freed by the kernel.
    directory = scratch / "killed-holder"
    admission, clock = admission_in(directory, Readings())
    holders = [subprocess.Popen(
        [sys.executable, "-c",
         "import fcntl, sys, time\n"
         "handle = open(sys.argv[1], 'a')\n"
         "fcntl.flock(handle.fileno(), fcntl.LOCK_EX)\n"
         "print('held', flush=True)\n"
         "time.sleep(60)\n",
         str(directory / f"{runner.TEST_SUITE_ADMISSION_SLOT_FILE_PREFIX}{number:02d}")],
        stdout=subprocess.PIPE, text=True) for number in range(ceiling)]
    for holder in holders:
        holder.stdout.readline()
    slot, why = admission.take_a_start_and_a_slot()
    held_by_others = slot is None
    for holder in holders:
        holder.kill()
        holder.wait()
    free_starts(directory)
    slot, why = admission.take_a_start_and_a_slot()
    check("slots held by processes that are then killed are free again",
          held_by_others and slot is not None, why)
    if slot is not None:
        slot.close()

    # --- At most so many starts a second -------------------------------------
    directory = scratch / "rate"
    admission, clock = admission_in(directory, Readings())
    per_second = runner.TEST_SUITE_ADMISSION_STARTS_PER_SECOND
    slots = []
    for _ in range(per_second):
        slot, why = admission.take_a_start_and_a_slot()
        slots.append(slot)
    slot, why = admission.take_a_start_and_a_slot()
    check(f"after {per_second} starts in one second, the next suite is held back",
          all(slots) and slot is None and "second" in (why or ""), why)
    clock.now += 1.0
    later, why = admission.take_a_start_and_a_slot()
    check("a second later, the next suite may start", later is not None, why)
    for handle in [*slots, later]:
        if handle is not None:
            handle.close()

    # --- Suites run outside the test sandbox ---------------------------------
    directory = scratch / "outside"
    order = []
    admission, clock = admission_in(directory, Readings())
    original_open_locked = admission.open_locked

    def noting_open_locked(path, blocking):
        order.append(pathlib.Path(path).name)
        return original_open_locked(path, blocking)

    admission.open_locked = noting_open_locked
    with admission.admitted("outside-test.py", outside_the_test_sandbox=True):
        pass
    check("a suite run outside the test sandbox takes the lock those suites share before "
          "it takes a slot",
          order and order[0] == runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX_LOCK_FILE_NAME
          and any(name.startswith(runner.TEST_SUITE_ADMISSION_SLOT_FILE_PREFIX)
                  for name in order[1:]), order)

    directory = scratch / "outside-held"
    lock_path = directory / runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX_LOCK_FILE_NAME
    directory.mkdir()
    other = open(lock_path, "a")
    fcntl.flock(other.fileno(), fcntl.LOCK_EX)
    said = []
    admission, clock = admission_in(directory, Readings(), said)
    slots_while_waiting = []

    def run_outside_suite():
        with admission.admitted("outside-test.py", outside_the_test_sandbox=True):
            pass

    waiter = threading.Thread(target=run_outside_suite)
    waiter.start()
    time.sleep(0.5)
    for number in range(ceiling):
        probe = directory / f"{runner.TEST_SUITE_ADMISSION_SLOT_FILE_PREFIX}{number:02d}"
        if probe.exists():
            with open(probe, "a") as handle:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    slots_while_waiting.append(probe.name)
    other.close()
    waiter.join(10)
    check("while another run's suite outside the test sandbox holds that lock, a suite "
          "outside waits for it holding no slot, and says what it waits for",
          not slots_while_waiting and not waiter.is_alive()
          and any("outside the test sandbox" in line for line in said),
          (slots_while_waiting, said))

    # --- Once a minute, what the suites wait for -----------------------------
    directory = scratch / "report-interval"
    said = []
    readings = Readings(cpu=90.0)
    admission, clock = admission_in(directory, readings, said)
    waits = {"count": 0}

    def free_after_three_minutes():
        waits["count"] += 1
        if clock.now >= 1000.0 + 180:
            readings.cpu = 10.0

    clock.on_sleep = free_after_three_minutes
    with admission.admitted("slow-start-test.py") as waited:
        pass
    check("a suite held back for three minutes is reported once a minute, not on every "
          "try", 3 <= len(said) <= 4 and waits["count"] > 100, (len(said), waits["count"]))
    check("the seconds a suite waited are what admission yields", waited >= 180, waited)

    # --- A failure to decide is reported, not waited out ---------------------
    blocked = scratch / "not-a-directory"
    blocked.write_text("")
    try:
        runner.MachineWideTestSuiteAdmission(blocked / "admission", Readings(), print)
        raised = None
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        raised = str(error)
    check("an admission directory that cannot be made is reported as an admission failure",
          raised is not None and "admission" in raised, raised)

    directory = scratch / "unopenable-slot"
    admission, clock = admission_in(directory, Readings())
    (directory / f"{runner.TEST_SUITE_ADMISSION_SLOT_FILE_PREFIX}00").mkdir()
    try:
        with admission.admitted("a-test.py"):
            pass
        raised = None
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        raised = str(error)
    check("a slot file that cannot be opened is reported as an admission failure, naming "
          "the file", raised is not None and "slot-00" in raised, raised)

    # --- Machine readings ------------------------------------------------------
    class Psutil:
        def __init__(self, values=(30.0, 60.0, 90.0, 20.0, 50.0, 70.0)):
            self.values = list(values)

        def cpu_percent(self, interval=None):
            # The last value repeats, so the readings run on after the listed ones.
            return self.values.pop(0) if len(self.values) > 1 else self.values[0]

        def virtual_memory(self):
            class Memory:
                available = 33 * GB
            return Memory()

    readings_file = scratch / "machine-cpu-and-memory-readings.tsv"
    readings = runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(
        Psutil(), readings_file, interval=0.01, average_seconds=0.05)
    readings.start()
    time.sleep(0.3)
    readings.stop()
    rows = readings_file.read_text().splitlines()
    check("the machine readings file has a header and one row per reading, each with CPU, "
          "available memory and load",
          len(rows) >= 6 and all(len(row.split("\t")) == 4 for row in rows[1:])
          and rows[1].split("\t")[2] == str(33 * GB), rows[:3])
    check("the CPU average is over the last few readings only, so earlier ones drop out",
          abs(readings.cpu_percent_average() - 70.0) < 1e-9, readings.cpu_percent_average())

    class FailingPsutil(Psutil):
        def cpu_percent(self, interval=None):
            if interval is None:
                raise RuntimeError("the CPU counters vanished")
            return 10.0

    readings = runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(
        FailingPsutil(), None, interval=0.01)
    readings.start()
    time.sleep(0.2)
    readings.stop()
    try:
        readings.cpu_percent_average()
        raised = None
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        raised = str(error)
    check("readings that stop with an error make admission fail, naming the error, rather "
          "than decide on old readings", raised is not None and "vanished" in raised, raised)

    class FirstReadingFails(Psutil):
        def cpu_percent(self, interval=None):
            raise RuntimeError("no CPU counters at all")

    try:
        runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(
            FirstReadingFails(), None, interval=0.01).start()
        raised = None
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        raised = str(error)
    check("a first reading that fails is an admission failure naming the error, not a "
          "traceback", raised is not None and "no CPU counters" in raised, raised)

    class MemoryFails(Psutil):
        def virtual_memory(self):
            raise RuntimeError("no memory counters")

    sampler = runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(
        MemoryFails(), None, interval=0.01)
    try:
        sampler.available_memory_bytes()
        raised = None
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        raised = str(error)
    check("available memory that cannot be read is an admission failure naming the error",
          raised is not None and "no memory counters" in raised, raised)

    # --- Start times on a clock every run shares, which never steps back -----------
    check("start times are read on the monotonic clock, which every process on Linux shares",
          runner.MachineWideTestSuiteAdmission.__init__.__defaults__[-1] is time.monotonic)
    directory = scratch / "clock-stepped-back"
    admission, clock = admission_in(directory, Readings())
    directory.mkdir(exist_ok=True)
    (directory / runner.TEST_SUITE_ADMISSION_START_TIMES_FILE_NAME).write_text(
        "".join(f"{clock.now + 500.0!r}\n"
                for _ in range(runner.TEST_SUITE_ADMISSION_STARTS_PER_SECOND)))
    slot, why = admission.take_a_start_and_a_slot()
    check("starts recorded later than now, as after a clock stepped back, do not hold "
          "admission back", slot is not None, why)
    if slot is not None:
        slot.close()

    # --- psutil missing ----------------------------------------------------------
    hidden = scratch / "no-psutil"
    hidden.mkdir()
    (hidden / "psutil.py").write_text("raise ImportError('psutil is hidden by this test')\n")
    answer = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util, sys\n"
         f"sys.path.insert(0, {str(hidden)!r})\n"
         f"spec = importlib.util.spec_from_file_location('runner', {str(RUNNER_PATH)!r})\n"
         "runner = importlib.util.module_from_spec(spec)\n"
         "spec.loader.exec_module(runner)\n"
         "module, refusal = runner.psutil_imported_or_why_not()\n"
         "print(module is None)\n"
         "print(refusal)\n"],
        capture_output=True, text=True, check=False)
    check("without psutil, the runner refuses with what to install and how",
          answer.stdout.startswith("True")
          and "check-and-install.py" in answer.stdout and "not run" in answer.stdout,
          answer.stdout + answer.stderr)

    # --- The cgroup scope ------------------------------------------------------
    why = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none(which=lambda name: None)
    check("without systemd-run on PATH, the reason says so",
          why is not None and "not on PATH" in why, why)

    why = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none(
        which=lambda name: None if name == "setpriv" else f"/usr/bin/{name}")
    check("without setpriv, which ties the counting shell's life to this program's, the "
          "reason names it", why is not None and "setpriv" in why, why)

    class Failed:
        returncode, stdout, stderr = 1, "", "Failed to connect to bus: No medium found"

    why = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none(
        which=lambda name: "/usr/bin/systemd-run", runner=lambda *a, **k: Failed())
    check("a systemd-run that cannot start a scope gives its own error as the reason",
          why is not None and "No medium found" in why, why)

    def os_error(*arguments, **options):
        raise OSError("Permission denied")

    why = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none(
        which=lambda name: "/usr/bin/systemd-run", runner=os_error)
    check("a systemd-run that cannot be started at all gives the error as the reason",
          why is not None and "Permission denied" in why, why)

    check("the cgroup counters give the suite's CPU seconds and peak memory",
          runner.cpu_seconds_and_peak_memory_from_suite_cgroup_statistics(
              "usage_usec 2500000\nuser_usec 2000000\nsystem_usec 500000\n"
              "memory.peak 123456789\n") == (2.5, 123456789, None))
    cpu, peak, why = runner.cpu_seconds_and_peak_memory_from_suite_cgroup_statistics(
        "cat: /sys/fs/cgroup/x/memory.peak: No such file or directory\n")
    check("counters that could not be read leave the numbers out and say why",
          cpu is None and peak is None and "No such file" in why, why)
    cpu, peak, why = runner.cpu_seconds_and_peak_memory_from_suite_cgroup_statistics("")
    check("counters that were never written leave the numbers out and say why",
          cpu is None and peak is None and "not written" in why, why)

    # --- Case lines, timed as they arrive ----------------------------------------
    repository = scratch / "repository"
    repository.mkdir()
    (repository / "timed-test.py").write_text(
        "import time\n"
        "print('PASS  first case')\n"
        "time.sleep(0.4)\n"
        "print('FAIL  second case: it broke')\n"
        "print('      a detail line')\n"
        "print('ok: third case')\n"
        "raise SystemExit(1)\n")
    log_dir = scratch / "logs"
    log_dir.mkdir()
    result = runner.run_one_suite(repository, sys.executable, "timed-test.py", log_dir)
    cases = result["cases"]
    check("each PASS, FAIL and ok line is a case, with its name and a FAIL's detail",
          [(case["verdict"], case["name"], case["detail"]) for case in cases]
          == [("PASS", "first case", ""), ("FAIL", "second case", "it broke"),
              ("PASS", "third case", "")], cases)
    check("a case's seconds run from the case line before it, as the lines arrive",
          len(cases) == 3 and cases[1]["seconds"] >= 0.35 and cases[0]["seconds"] < 0.35,
          [case["seconds"] for case in cases])
    check("the suite's output still reaches its log whole",
          "a detail line" in result["log"].read_text(), result["log"].read_text())

    leaver = repository / "leaves-a-writer-test.py"
    leaver.write_text(
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "print('PASS  started a writer')\n")
    original_drain = runner.TEST_SUITE_OUTPUT_DRAIN_SECONDS
    runner.TEST_SUITE_OUTPUT_DRAIN_SECONDS = 1
    began = time.monotonic()
    leaver_result = runner.run_one_suite(repository, sys.executable, leaver.name,
                                         log_dir)
    runner.TEST_SUITE_OUTPUT_DRAIN_SECONDS = original_drain
    check("a process the suite leaves holding its output open does not hold up the run, "
          "and the result says so",
          time.monotonic() - began < 10 and leaver_result["output_note"] is not None
          and leaver_result["exit"] == 0, leaver_result)

    # --- The run's records: case times, suite resources, JUnit XML, failure history ---
    result.update(kind="test sandbox", admission_wait=1.5, cpu_seconds=0.7,
                  peak_memory_bytes=4000000, resources_note=None)
    passed = {"suite": "quiet-test.py", "exit": 0, "seconds": 0.2, "log": log_dir / "q.log",
              "skips": [], "cases": [], "kind": "test sandbox", "admission_wait": 0.0,
              "cpu_seconds": None, "peak_memory_bytes": None,
              "resources_note": "systemd-run is not on PATH"}
    records = scratch / "records"
    records.mkdir()
    runner.write_case_times_suite_resources_and_junit_xml_of_run(records, [result, passed])
    times = (records / runner.TEST_CASE_TIMES_FILE_NAME).read_text().splitlines()
    check("the case times file has one row per case line",
          len(times) == 4 and times[2].split("\t")[:2] == ["timed-test.py", "FAIL"], times)
    resources = (records / runner.TEST_SUITE_RESOURCE_USE_FILE_NAME).read_text().splitlines()
    check("the suite resources file has each suite's kind, admission wait, CPU seconds and "
          "peak memory, or why they are missing",
          resources[1].split("\t")[1:7] == ["test sandbox", "1", f"{result['seconds']:.3f}",
                                             "1.500", "0.700", "4000000"]
          and resources[2].endswith("systemd-run is not on PATH"), resources)
    junit = xml.etree.ElementTree.parse(records / runner.JUNIT_XML_FILE_NAME).getroot()
    suites = {suite.get("name"): suite for suite in junit.iter("testsuite")}
    timed = suites.get("timed-test.py")
    quiet = suites.get("quiet-test.py")
    check("the JUnit XML has a testsuite per suite and a testcase per case line, the "
          "failing one with its detail",
          timed is not None and timed.get("tests") == "3" and timed.get("failures") == "1"
          and [case.find("failure").get("message") for case in timed.iter("testcase")
               if case.find("failure") is not None] == ["it broke"],
          xml.etree.ElementTree.tostring(junit)[:600])
    check("a suite that printed no case line is one testcase, judged by its exit code",
          quiet is not None and quiet.get("tests") == "1"
          and quiet.find("testcase").find("failure") is None,
          xml.etree.ElementTree.tostring(junit)[:600])

    crashed = dict(passed, suite="crashed-test.py", exit=-9,
                   cases=[{"verdict": "PASS", "name": "only", "detail": "", "began": 0.0,
                           "ended": 0.1, "seconds": 0.1, "unix_time": 0.0}])
    runner.write_case_times_suite_resources_and_junit_xml_of_run(records, [crashed])
    crashed_suite = xml.etree.ElementTree.parse(
        records / runner.JUNIT_XML_FILE_NAME).getroot().find("testsuite")
    check("a suite that fails after its last case line gets a failing testcase naming how "
          "it ended",
          any(case.find("failure") is not None and "SIGKILL" in case.find("failure").get("message")
              for case in crashed_suite.iter("testcase")),
          xml.etree.ElementTree.tostring(crashed_suite))

    history = scratch / "history" / runner.TEST_CASE_FAILURE_HISTORY_FILE_NAME
    runner.append_test_case_failure_history(history, repository, "abc123", "topic-branch",
                                            records, [result, passed, crashed])
    entries = [json.loads(line) for line in history.read_text().splitlines()]
    check("the failure history gets each failing case, and a suite that failed with no "
          "failing case line, with commit and branch",
          [(entry["suite"], entry["case"]) for entry in entries]
          == [("timed-test.py", "second case"), ("crashed-test.py", None)]
          and all(entry["commit"] == "abc123" and entry["branch"] == "topic-branch"
                  for entry in entries), entries)

    # --- A suite in a cgroup scope of its own gets its counters, whatever descriptor ---
    cgroup_unavailable = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none()
    if cgroup_unavailable is None:
        # Hold descriptors open, so the one the counters go to is numbered above 9, which a
        # shell such as dash cannot name.
        held_open = [open(os.devnull) for _ in range(12)]
        try:
            scoped = runner.run_one_suite(repository, sys.executable, "timed-test.py", log_dir,
                                          in_cgroup_scope=True)
        finally:
            for handle in held_open:
                handle.close()
        check("a suite run in a cgroup scope of its own gets its CPU seconds and peak memory, "
              "and keeps its own exit code",
              scoped["cpu_seconds"] is not None and scoped["peak_memory_bytes"]
              and scoped["exit"] == 1, scoped)
    else:
        print(f"SKIP  the cgroup scope case: {cgroup_unavailable}")

    # --- On the Mac, the suite's output goes straight to its log, as it always did ---
    mac_result = runner.run_one_suite(repository, sys.executable, "timed-test.py", log_dir,
                                      platform="darwin")
    check("on the Mac no case line is timed, and the output reaches the log whole",
          mac_result["cases"] == [] and mac_result["exit"] == 1
          and "a detail line" in mac_result["log"].read_text(), mac_result)

    # --- The suites' environment carries no credential -----------------------------
    saved = {name: os.environ.get(name) for name in
             ("GH_TOKEN", "GITHUB_TOKEN", "ANTHROPIC_API_KEY", "SOME_SERVICE_SECRET",
              "DB_PASSWORD", "AWS_CREDENTIALS", "KEEP_THIS_ONE")}
    try:
        for name in saved:
            os.environ[name] = "value-of-" + name
        environment = runner.launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed()
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    check("a suite is launched without any variable that carries a credential, and with "
          "the others",
          not any(name in environment for name in saved if name != "KEEP_THIS_ONE")
          and environment.get("KEEP_THIS_ONE") == "value-of-KEEP_THIS_ONE",
          sorted(name for name in saved if name in environment))

    # --- A checkout whose git directory cannot be found gets no test sandbox ---------
    original_common = runner.git_common_directory_of_checkout
    runner.git_common_directory_of_checkout = lambda top: None
    try:
        runner.bwrap_arguments_for_one_suites_test_sandbox(repository)
        raised = None
    except runner.SignalSandboxCouldNotStart as error:
        raised = str(error)
    finally:
        runner.git_common_directory_of_checkout = original_common
    check("when the checkout's git common directory cannot be found, the test sandbox is "
          "refused rather than built without its read-only git directory",
          raised is not None and "git common directory" in raised, raised)

    # --- Every failure of admission or of a test sandbox ends the run with exit 2 ---
    run_repository = scratch / "run-repository"
    run_repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=run_repository, check=True)
    (run_repository / "a-test.py").write_text("print('PASS  only case')\n")
    subprocess.run(["git", "add", "."], cwd=run_repository, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                    "-m", "start"], cwd=run_repository, check=True)

    @contextlib.contextmanager
    def replaced(**names):
        originals = {name: getattr(runner, name) for name in names}
        for name, value in names.items():
            setattr(runner, name, value)
        try:
            yield
        finally:
            for name, value in originals.items():
                setattr(runner, name, value)

    def main_with(label, **names):
        run_scratch = scratch / f"main-{label}"
        run_scratch.mkdir()
        printed_out, printed_err = io.StringIO(), io.StringIO()
        with replaced(**names), contextlib.redirect_stdout(printed_out), \
                contextlib.redirect_stderr(printed_err):
            code = runner.main(["--checkout", str(run_repository),
                                "--lock-file", str(run_scratch / "run.lock"),
                                "--log-dir", str(run_scratch / "logs"),
                                "--recorded-inputs-directory", str(run_scratch / "recorded")])
        return code, printed_out.getvalue() + printed_err.getvalue(), run_scratch / "logs"

    as_if_bwrap = {"signal_sandbox": lambda **options: (("/usr/bin/bwrap",), None),
                   "TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW": 101,
                   "TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE": -1}

    def no_git_directory(top):
        return None

    code, printed, _ = main_with("no-git-directory", git_common_directory_of_checkout=no_git_directory,
                                 **as_if_bwrap)
    check("a test sandbox that cannot be built for the checkout stops the run before any "
          "suite, with exit 2 and the reason",
          code == runner.EXIT_COULD_NOT_RUN and "git common directory" in printed
          and "Traceback" not in printed, (code, printed[-800:]))

    def first_reading_fails(self):
        raise runner.MachineWideTestSuiteAdmissionCouldNotDecide("the first reading failed: x")

    sampler_class = runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler
    original_start = sampler_class.start
    sampler_class.start = first_reading_fails
    try:
        code, printed, _ = main_with("first-reading", **as_if_bwrap)
    finally:
        sampler_class.start = original_start
    check("a first machine reading that fails ends the run with exit 2 and the reason on "
          "its own line",
          code == runner.EXIT_COULD_NOT_RUN
          and "admission could not start: the first reading failed" in printed
          and "Traceback" not in printed, (code, printed[-800:]))

    def admission_breaks(*arguments, **options):
        raise runner.MachineWideTestSuiteAdmissionCouldNotDecide("slot-07 could not be opened")

    code, printed, _ = main_with("mid-run", run_one_suite=admission_breaks, **as_if_bwrap)
    check("admission that fails while suites run ends the run with exit 2, the reason on "
          "its own line, not a traceback with exit 1",
          code == runner.EXIT_COULD_NOT_RUN and "admission failed: slot-07" in printed
          and "Fix what it names" in printed and "Traceback" not in printed,
          (code, printed[-800:]))

    def cover_breaks(*arguments, **options):
        raise runner.SignalSandboxCouldNotStart("the empty file that covers each credential "
                                                "file is not empty; delete it")

    code, printed, _ = main_with("cover", run_one_suite=cover_breaks, **as_if_bwrap)
    check("a test sandbox that fails while suites run ends the run with exit 2 and the "
          "reason, not a traceback",
          code == runner.EXIT_COULD_NOT_RUN and "delete it" in printed
          and "Traceback" not in printed, (code, printed[-800:]))

    code, printed, logs = main_with(
        "no-bwrap", signal_sandbox=lambda **options: ((), "bwrap is not on PATH"))
    check("without test sandboxes there is no admission, and no case times, JUnit XML or "
          "failure history are written",
          code == runner.EXIT_ALL_PASSED and not (logs / runner.JUNIT_XML_FILE_NAME).exists()
          and runner.ADMISSION_WAITED_LINE_PREFIX not in printed, (code, printed[-800:]))

    # --- -j where admission decides --------------------------------------------
    check("where admission decides, every suite of the run may wait for admission at once",
          runner.suites_run_at_once(None, 144, 16, admission_decides=True) == 64
          and runner.suites_run_at_once(None, 10, 16, admission_decides=True) == 10
          and runner.suites_run_at_once(3, 144, 16, admission_decides=True) == 3)

print(f"{len(failures)} failed" if failures else "all cases passed")
sys.exit(1 if failures else 0)
