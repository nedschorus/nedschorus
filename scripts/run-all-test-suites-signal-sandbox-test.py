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


def raise_os_error_early(command, **options):
    raise OSError("Exec format error")


# --- Which prefix, or why none ---------------------------------------------

prefix, why = runner.signal_sandbox(platform="freebsd14", environment={})
check("on a platform with no signal sandbox, suites run unconfined and the reason names it",
      prefix == () and "freebsd14" in why, (prefix, why))

# macOS, with sandbox-exec stood in for: any existing file serves as its path.
mac_trials = []
prefix, why = runner.signal_sandbox(
    platform="darwin", environment={}, sandbox_exec=sys.executable, outside_process_id=4242,
    runner=lambda command, **options: mac_trials.append(command) or Completed(0))
check("on macOS, the prefix is sandbox-exec with the signal-only profile, marking the inside "
      "and naming the outside process",
      prefix[:3] == (sys.executable, "-p", runner.SIGNAL_SANDBOX_MACOS_PROFILE)
      and prefix[3] == "/usr/bin/env"
      and f"{runner.SIGNAL_SANDBOX_INSIDE_VARIABLE}=1" in prefix
      and f"{runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE}=4242" in prefix and why is None,
      prefix)
check("on macOS, the trial runs inside that prefix before any suite and signals the "
      "outside process",
      len(mac_trials) == 1 and mac_trials[0][:len(prefix)] == list(prefix)
      and mac_trials[0][-1] == runner.SIGNAL_SANDBOX_MACOS_TRIAL_SOURCE, mac_trials)
check("on macOS, the outside process defaults to the program building the prefix",
      f"{runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE}={os.getpid()}" in runner.signal_sandbox(
          platform="darwin", environment={}, sandbox_exec=sys.executable,
          runner=lambda command, **options: Completed(0))[0])
prefix, why = runner.signal_sandbox(
    platform="darwin", environment={runner.SIGNAL_SANDBOX_INSIDE_VARIABLE: "1"},
    sandbox_exec="/no/such/sandbox-exec")
check("on macOS inside a sandbox already, no second sandbox is started",
      prefix == () and why is None, (prefix, why))

for case_name, options, expected in (
        ("on macOS, a missing sandbox-exec is an error, never an unconfined run",
         {"sandbox_exec": "/no/such/sandbox-exec"}, "is not on this Mac"),
        ("on macOS, a trial whose signal got through is an error naming what it printed",
         {"sandbox_exec": sys.executable, "runner": lambda command, **options: Completed(
             1, stderr="a signal from inside the sandbox reached process 4242 outside it")},
         "reached process 4242"),
        ("on macOS, a sandbox-exec that cannot be executed is an error",
         {"sandbox_exec": sys.executable, "runner": raise_os_error_early},
         "Exec format error")):
    try:
        runner.signal_sandbox(platform="darwin", environment={}, outside_process_id=4242,
                              **options)
    except runner.SignalSandboxCouldNotStart as error:
        check(case_name, expected in str(error), str(error))
    else:
        check(case_name, False, "no exception")

# The trial's own source, run here without a sandbox: a signal to this process gets
# through, so the trial must exit nonzero; SIGWINCH is ignored, so nothing else happens.
trial = subprocess.run(
    [sys.executable, "-c", runner.SIGNAL_SANDBOX_MACOS_TRIAL_SOURCE], capture_output=True,
    text=True, check=False,
    env={**os.environ, runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE: str(os.getpid())})
check("unconfined, the trial's signal to the outside process gets through and the trial fails",
      trial.returncode != 0 and "reached process" in trial.stderr,
      (trial.returncode, trial.stderr))

# macOS refuses to exec the setuid /bin/ps inside sandbox-exec; suites that call ps
# fail with "Operation not permitted" unless the profile runs ps outside the sandbox.
check("the macOS profile runs /bin/ps outside the sandbox and still refuses signals "
      "to processes outside it",
      runner.SIGNAL_SANDBOX_MACOS_PROFILE.endswith(
          '(allow process-exec (literal "/bin/ps") (with no-sandbox))')
      and "(deny signal)(allow signal (target same-sandbox))" in runner.SIGNAL_SANDBOX_MACOS_PROFILE,
      runner.SIGNAL_SANDBOX_MACOS_PROFILE)

check("only bwrap reports a suite killed by signal N as exit 128+N",
      runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(("/usr/bin/bwrap", "--unshare-pid"))
      and not runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(
          ("/usr/bin/sandbox-exec", "-p", runner.SIGNAL_SANDBOX_MACOS_PROFILE))
      and not runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(()))
check("the report line for sandbox-exec does not claim a PID namespace",
      "PID namespace" not in runner.signal_sandbox_line(
          ("/usr/bin/sandbox-exec", "-p", "x"), None)
      and "refuses its signals" in runner.signal_sandbox_line(
          ("/usr/bin/sandbox-exec", "-p", "x"), None))

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

# --- What a run's report says about the sandbox -------------------------------


def scratch_checkout(scratch, suites):
    """A git checkout holding the given suites, each printing that it ran."""
    repository = scratch / "repo"
    for suite in suites:
        (repository / suite).parent.mkdir(parents=True, exist_ok=True)
        (repository / suite).write_text("print('ran')\n")
    for git_arguments in (["init", "-q"], ["add", "-A"],
                          ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"]):
        subprocess.run(["git", "-C", str(repository), *git_arguments],
                       capture_output=True, check=True)
    return repository


def run_runner(scratch, repository, path):
    environment = {name: value for name, value in os.environ.items()
                   if name != runner.SIGNAL_SANDBOX_INSIDE_VARIABLE}
    environment["PATH"] = path
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--checkout", str(repository),
         "--log-dir", str(scratch / "logs"),
         "--lock-file", str(scratch / "run.lock"),
         "--recorded-inputs-directory", str(scratch / "recordings")],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL, check=False)
    report_file = scratch / "logs" / runner.REPORT_FILE_NAME
    report = report_file.read_text() if report_file.exists() else ""
    return completed, report


OUTSIDE_SUITE = "scripts/mac-window-opened-for-ned-box-forced-command-test.py"

if sys.platform.startswith("linux"):
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = pathlib.Path(scratch_name)
        # Every command on PATH but bwrap, so the run finds git and sh and no sandbox.
        path_without_bwrap = scratch / "bin"
        path_without_bwrap.mkdir()
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            if not directory or not os.path.isdir(directory):
                continue
            for entry in os.scandir(directory):
                target = path_without_bwrap / entry.name
                if entry.name != "bwrap" and not os.path.lexists(target):
                    target.symlink_to(entry.path)
        repository = scratch_checkout(scratch, ["a-test.py"])
        completed, report = run_runner(scratch, repository, str(path_without_bwrap))
        without = "suites run WITHOUT the signal sandbox"
        check("without bwrap, the run's output and report.txt say the suites ran without "
              "the sandbox, and why",
              completed.returncode == 0
              and all(without in text and "bwrap is not on PATH" in text
                      for text in (completed.stdout, report)),
              (completed.returncode, completed.stdout[-600:], report[-600:]))
        check("without bwrap, nothing in the report claims the suites were confined",
              "PID namespace" not in report, report[-600:])

    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = pathlib.Path(scratch_name)
        fake_bin = scratch / "bin"
        fake_bin.mkdir()
        # Stands in for a working bwrap: skips the sandbox's own arguments, names the
        # suite's process on the status descriptor as bwrap does, and runs the suite.
        (fake_bin / "bwrap").write_text(
            "#!/bin/sh\n"
            "status_fd=\n"
            "while [ $# -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    --dev-bind|--setenv) shift 3 ;;\n"
            "    --proc) shift 2 ;;\n"
            "    --json-status-fd) status_fd=$2; shift 2 ;;\n"
            "    --unshare-pid|--die-with-parent) shift ;;\n"
            "    *) break ;;\n"
            "  esac\n"
            "done\n"
            "[ -n \"$status_fd\" ] && eval \"echo '{\\\"child-pid\\\": $$}' >&$status_fd\"\n"
            "exec \"$@\"\n")
        (fake_bin / "bwrap").chmod(0o755)
        repository = scratch_checkout(scratch, ["a-test.py", OUTSIDE_SUITE])
        completed, report = run_runner(
            scratch, repository, f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
        check("with the sandbox on, report.txt says each suite runs in its own PID namespace",
              completed.returncode == 0
              and f"each suite runs in its own PID namespace: {fake_bin / 'bwrap'}" in report,
              (completed.returncode, report[-600:]))
        check("with the sandbox on, report.txt names a suite that runs outside it, and why",
              f"{OUTSIDE_SUITE} runs WITHOUT the signal sandbox: "
              f"{runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX[OUTSIDE_SUITE]}" in report,
              report[-600:])
else:
    print("SKIP  the report's sandbox lines: bwrap is used only on Linux")

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
    (scratch / "exits-143-test.sh").write_text("exit 143\n")
    # Stand in for bwrap's report of a signalled command: run it, then exit 128+15.
    for stand_in in ("bwrap", "sandbox-exec"):
        (scratch / stand_in).write_text('#!/bin/sh\n"$@"\nexit $((128 + 15))\n')
        (scratch / stand_in).chmod(0o755)
    fake_prefix = (str(scratch / "bwrap"),)
    result = runner.run_one_suite(scratch, sys.executable, "dies-test.sh", scratch,
                                  sandbox_prefix=fake_prefix)
    check("a sandboxed suite killed by SIGTERM (bwrap exits 143) is reported as killed by SIGTERM",
          runner.describe_exit(result["exit"]) == "killed by SIGTERM", result["exit"])
    # sandbox-exec replaces itself with the suite, so 143 there is the suite's own exit.
    passthrough = runner.run_one_suite(scratch, sys.executable, "exits-143-test.sh", scratch,
                                       sandbox_prefix=(str(scratch / "sandbox-exec"),))
    check("under sandbox-exec, a suite's own exit 143 is reported as exit 143, not as a signal",
          passthrough["exit"] == 143, passthrough["exit"])
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


# Signals the sleeper this file started and this file's own process, which is the
# probe's parent, then stops a child of its own, which the sandbox must allow.
MACOS_PROBE = (
    "import os, signal, subprocess, sys\n"
    "results = []\n"
    "for target, number in ((int(sys.argv[1]), signal.SIGTERM),\n"
    "                       (os.getppid(), signal.SIGWINCH)):\n"
    "    try:\n"
    "        os.kill(target, number)\n"
    "    except PermissionError:\n"
    "        results.append('refused')\n"
    "    else:\n"
    "        results.append('signalled')\n"
    "child = subprocess.Popen(['/bin/sleep', '60'])\n"
    "child.terminate()\n"
    "results.append('own child stopped' if child.wait() == -signal.SIGTERM\n"
    "               else 'own child not stopped')\n"
    "print(' '.join(results))\n")

if sys.platform != "darwin":
    print("SKIP  the end-to-end sandbox-exec case: sandbox-exec exists only on macOS")
# Inside an inherited sandbox, the probe signals the process outside it that the
# runner named, and this file's own process, which shares the sandbox, is allowed.
MACOS_INHERITED_SANDBOX_PROBE = (
    "import os, signal, subprocess, sys\n"
    "try:\n"
    "    os.kill(int(sys.argv[1]), signal.SIGWINCH)\n"
    "except PermissionError:\n"
    "    result = 'refused'\n"
    "else:\n"
    "    result = 'signalled'\n"
    "child = subprocess.Popen(['/bin/sleep', '60'])\n"
    "child.terminate()\n"
    "print(result, 'own child stopped' if child.wait() == -signal.SIGTERM\n"
    "      else 'own child not stopped')\n")


def macos_case_inside_inherited_sandbox(environment, run=subprocess.run):
    """Return (passed, detail) for the macOS case when the runner already confined this file.

    macOS refuses a second sandbox-exec inside the first, so the case relies on the
    sandbox it inherited and signals the outside process the runner named.
    """
    outside = environment.get(runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE, "")
    if not outside.isdigit() or int(outside) <= 1:
        return False, f"{runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE} is {outside!r}"
    probed = run([sys.executable, "-c", MACOS_INHERITED_SANDBOX_PROBE, outside],
                 capture_output=True, text=True, timeout=60, check=False)
    return probed.stdout.strip() == "refused own child stopped", (probed.stdout, probed.stderr)


def recorded_probe_run(stdout):
    calls = []

    def run(command, **keywords):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout, "")
    return run, calls


run, calls = recorded_probe_run("refused own child stopped\n")
passed, detail = macos_case_inside_inherited_sandbox(
    {runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE: "4242"}, run=run)
check("inside an inherited macOS sandbox, the case starts no second sandbox-exec and "
      "signals the outside process the runner named",
      passed and len(calls) == 1 and "sandbox-exec" not in " ".join(calls[0])
      and calls[0][-1] == "4242", (passed, detail, calls))
passed, detail = macos_case_inside_inherited_sandbox({}, run=recorded_probe_run("")[0])
check("inside an inherited macOS sandbox with no outside process named, the case fails",
      not passed, detail)
passed, detail = macos_case_inside_inherited_sandbox(
    {runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE: "4242"},
    run=recorded_probe_run("signalled own child stopped\n")[0])
check("inside an inherited macOS sandbox, a signal that reaches the outside process fails "
      "the case", not passed, detail)

if sys.platform == "darwin" and os.environ.get(runner.SIGNAL_SANDBOX_INSIDE_VARIABLE):
    passed, detail = macos_case_inside_inherited_sandbox(os.environ)
    check("on macOS, inside the runner's sandbox-exec, a signal to the runner outside it is "
          "refused, while the probe stops its own child", passed, detail)
elif sys.platform == "darwin":
    # Not confined yet: a process in a fresh sandbox-exec may signal neither this
    # file nor its sleeper.
    macos_prefix = runner.macos_signal_sandbox(
        subprocess.run, runner.SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC, os.getpid())
    sleeper = subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL)
    try:
        probed = subprocess.run([*macos_prefix, sys.executable, "-c", MACOS_PROBE,
                                 str(sleeper.pid)],
                                capture_output=True, text=True, timeout=60, check=False)
        time.sleep(0.5)
        sleeper_alive = sleeper.poll() is None
    finally:
        if sleeper.poll() is None:
            sleeper.kill()
        sleeper.wait()
    check("on macOS, inside sandbox-exec, signals to this file's sleeper and to this file, "
          "the probe's parent, are refused, while the probe stops its own child",
          probed.stdout.strip() == "refused refused own child stopped" and sleeper_alive,
          (probed.stdout, probed.stderr, sleeper_alive))
elif os.environ.get(runner.SIGNAL_SANDBOX_INSIDE_VARIABLE):
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
