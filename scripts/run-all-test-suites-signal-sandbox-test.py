#!/usr/bin/env python3
"""Tests for the signal sandbox scripts/run-all-test-suites.py puts each suite in.

The isolation cases signal only a sleeper this file starts itself, never -1,
0, 1 or any other process: if the sandbox did not work, the worst a case can
do is stop its own sleeper.

Run directly on Linux with bwrap, this file starts a fresh sandbox and shows a
command inside it cannot signal a process outside. Run by the runner, it is
already inside a sandbox, where bwrap cannot start again, so it shows instead
that no process outside its own namespace is visible.

Run: python3 scripts/run-all-test-suites-signal-sandbox-test.py   (exit 0 = all passed)
"""

import importlib.util
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time

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
MUTATION_SCRIPT_PATH = SCRIPTS_DIR / "pull-request-mutation-testing-survivors.py"

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
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
mutation = load("pull_request_mutation_testing_survivors", MUTATION_SCRIPT_PATH)


class Completed:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


# --- Which prefix, or why none ---------------------------------------------

prefix, why = runner.signal_sandbox(platform="darwin", environment={})
check("on macOS, suites run unconfined and the reason names the platform",
      prefix == () and "darwin" in why, (prefix, why))

prefix, why = runner.signal_sandbox(platform="linux", environment={}, which=lambda name: None)
check("on Linux without bwrap, suites run unconfined and the reason names bwrap",
      prefix == () and "bwrap" in why, (prefix, why))

prefix, why = runner.signal_sandbox(
    platform="linux", environment={runner.SIGNAL_SANDBOX_INSIDE_VARIABLE: "1"},
    which=lambda name: "/usr/bin/bwrap")
check("inside a sandbox already, no second sandbox is started and no reason is given",
      prefix == () and why is None, (prefix, why))

trials = []
prefix, why = runner.signal_sandbox(
    platform="linux", environment={}, which=lambda name: "/usr/bin/bwrap",
    runner=lambda command, **options: trials.append(command) or Completed(0))
check("with a working bwrap, the prefix unshares the PID namespace and marks the inside",
      prefix[0] == "/usr/bin/bwrap" and "--unshare-pid" in prefix
      and "--die-with-parent" in prefix
      and runner.SIGNAL_SANDBOX_INSIDE_VARIABLE in prefix and why is None, prefix)
check("bwrap is tried once with `true` before any suite runs",
      trials == [[*prefix, "true"]], trials)

try:
    runner.signal_sandbox(platform="linux", environment={}, which=lambda name: "/usr/bin/bwrap",
                          runner=lambda command, **options: Completed(1, stderr="bwrap: No permissions"))
except runner.SignalSandboxCouldNotStart as error:
    check("a bwrap that fails to start is an error naming what it printed, not a quiet fallback",
          "No permissions" in str(error) and "exited 1" in str(error), str(error))
else:
    check("a bwrap that fails to start is an error naming what it printed, not a quiet fallback",
          False, "no exception")


def raise_os_error(command, **options):
    raise OSError("Exec format error")


try:
    runner.signal_sandbox(platform="linux", environment={}, which=lambda name: "/usr/bin/bwrap",
                          runner=raise_os_error)
except runner.SignalSandboxCouldNotStart as error:
    check("a bwrap that cannot be executed is an error too", "Exec format error" in str(error),
          str(error))
else:
    check("a bwrap that cannot be executed is an error too", False, "no exception")

check("the report line for a run without the sandbox says so and why",
      "WITHOUT" in runner.signal_sandbox_line((), "bwrap is not on PATH")
      and "bwrap is not on PATH" in runner.signal_sandbox_line((), "bwrap is not on PATH"))
check("the refusal names the program that refused",
      runner.signal_sandbox_refusal("x", "some-program").startswith("some-program: not run"))

# --- The runner refuses when bwrap is on PATH but broken ---------------------

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    fake_bin = scratch / "bin"
    fake_bin.mkdir()
    fake_bwrap = fake_bin / "bwrap"
    fake_bwrap.write_text("#!/bin/sh\necho 'bwrap: No permissions to create a new namespace' >&2\n"
                          "exit 1\n")
    fake_bwrap.chmod(0o755)
    environment = {name: value for name, value in os.environ.items()
                   if name != runner.SIGNAL_SANDBOX_INSIDE_VARIABLE}
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
    # A scratch checkout with one suite, so a refusal that failed would run nothing real.
    repository = scratch / "repo"
    repository.mkdir()
    ran_marker = scratch / "a-suite-ran"
    (repository / "a-test.py").write_text(
        f"open({str(ran_marker)!r}, 'w').write('ran')\n")
    for git_arguments in (["init", "-q"], ["add", "a-test.py"],
                          ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"]):
        subprocess.run(["git", "-C", str(repository), *git_arguments], env=environment,
                       capture_output=True, check=True)
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--checkout", str(repository),
         "--log-dir", str(scratch / "logs"),
         "--lock-file", str(scratch / "run.lock"),
         "--recorded-inputs-directory", str(scratch / "recordings")],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL, check=False)
    if sys.platform.startswith("linux"):
        check("on Linux, a bwrap that fails to start stops the run with exit 2 before any suite runs",
              completed.returncode == runner.EXIT_COULD_NOT_RUN
              and "signal sandbox could not start" in completed.stderr
              and "No permissions" in completed.stderr
              and not ran_marker.exists(),
              (completed.returncode, completed.stderr[-600:]))
    else:
        print("SKIP  the broken-bwrap refusal: bwrap is used only on Linux")

# --- The mutation script's test command --------------------------------------

command = mutation.test_command_for(["a-test.py"], "/usr/bin/python3",
                                    ("/usr/bin/bwrap", "--unshare-pid", "--setenv", "X", "1"))
check("each mutant's suites run inside the sandbox prefix",
      command == "sh -c '/usr/bin/bwrap --unshare-pid --setenv X 1 /usr/bin/python3 -u a-test.py'",
      command)
check("without a sandbox, the mutant's test command is unchanged",
      mutation.test_command_for(["a-test.py"], "/usr/bin/python3")
      == "sh -c '/usr/bin/python3 -u a-test.py'")

# --- A signalled suite inside bwrap is reported as the signal ----------------

with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    (scratch / "dies-test.sh").write_text("kill -TERM $$\n")
    # Stands in for bwrap's report of a signalled command: run it, then exit 128+15.
    fake_prefix = ("sh", "-c", '"$@"; exit $((128 + 15))', "fake-bwrap")
    result = runner.run_one_suite(scratch, sys.executable, "dies-test.sh", scratch,
                                  sandbox_prefix=fake_prefix)
    check("a sandboxed suite killed by SIGTERM (bwrap exits 143) is reported as killed by SIGTERM",
          runner.describe_exit(result["exit"]) == "killed by SIGTERM", result["exit"])
    plain = runner.run_one_suite(scratch, sys.executable, "dies-test.sh", scratch)
    check("an unsandboxed suite's exit code is reported unchanged",
          plain["exit"] == -signal.SIGTERM, plain["exit"])

    marking_prefix = ("sh", "-c", 'echo PREFIXED; "$@"', "fake-bwrap")
    (scratch / "plain-test.sh").write_text("echo ran\n")
    inside = runner.run_one_suite(scratch, sys.executable, "plain-test.sh", scratch,
                                  sandbox_prefix=marking_prefix)
    check("an ordinary suite runs under the sandbox prefix",
          "PREFIXED" in inside["log"].read_text(), inside["log"].read_text())
    outside_suite = next(iter(runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX))
    (scratch / outside_suite).parent.mkdir(parents=True, exist_ok=True)
    (scratch / outside_suite).write_text("print('ran')\n")
    outside = runner.run_one_suite(scratch, sys.executable, outside_suite, scratch,
                                   sandbox_prefix=marking_prefix)
    check("a suite listed to run outside the sandbox runs without the prefix",
          "PREFIXED" not in outside["log"].read_text()
          and "ran" in outside["log"].read_text(), outside["log"].read_text())

for suite in runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX:
    check(f"the suite listed to run outside the sandbox exists: {suite}",
          (SCRIPTS_DIR.parent / suite).is_file())

command = mutation.test_command_for(["a-test.py", "b-test.py"], "/usr/bin/python3",
                                    ("/usr/bin/bwrap", "--unshare-pid"), {"b-test.py": "why"})
check("a mutant's suite listed to run outside the sandbox runs without the prefix",
      command == "sh -c '/usr/bin/bwrap --unshare-pid /usr/bin/python3 -u a-test.py "
                 "&& /usr/bin/python3 -u b-test.py'", command)


# --- Isolation ----------------------------------------------------------------

SIGNAL_THE_SLEEPER = (
    "import os, signal, sys\n"
    "try:\n"
    "    os.kill(int(sys.argv[1]), signal.SIGTERM)\n"
    "except ProcessLookupError:\n"
    "    print('NOT VISIBLE')\n"
    "    sys.exit(3)\n"
    "print('SIGNALLED')\n")


def sleeper_survives_signal_from(prefix):
    """Start our own sleeper, have a command under `prefix` SIGTERM it; return (alive, output)."""
    sleeper = subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL)
    try:
        completed = subprocess.run([*prefix, sys.executable, "-c", SIGNAL_THE_SLEEPER,
                                    str(sleeper.pid)],
                                   capture_output=True, text=True, timeout=60, check=False)
        time.sleep(0.5)
        return sleeper.poll() is None, completed.stdout + completed.stderr
    finally:
        if sleeper.poll() is None:
            sleeper.kill()
        sleeper.wait()


if os.environ.get(runner.SIGNAL_SANDBOX_INSIDE_VARIABLE):
    comm_of_one = pathlib.Path("/proc/1/comm").read_text().strip()
    visible = [entry.name for entry in pathlib.Path("/proc").iterdir() if entry.name.isdigit()]
    commands = []
    for pid in visible:
        try:
            commands.append(pathlib.Path(f"/proc/{pid}/comm").read_text().strip())
        except OSError:
            pass
    check("inside the runner's sandbox, process 1 is bwrap, not the machine's init",
          comm_of_one == "bwrap", comm_of_one)
    check("inside the runner's sandbox, no systemd process of the machine is visible",
          "systemd" not in commands, sorted(set(commands)))
else:
    sandbox_prefix, why = runner.signal_sandbox()
    alive, output = sleeper_survives_signal_from(())
    check("control: without the sandbox, the command does stop the sleeper",
          not alive and "SIGNALLED" in output, output)
    if sandbox_prefix:
        alive, output = sleeper_survives_signal_from(sandbox_prefix)
        check("inside the sandbox, a process outside cannot be signalled: the sleeper survives",
              alive and "NOT VISIBLE" in output, output)
    else:
        print(f"SKIP  sandbox isolation: suites run without the signal sandbox here: {why}")

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
