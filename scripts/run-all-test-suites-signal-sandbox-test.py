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
import socket
import shlex
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
# Runs the runner with admission's CPU and memory thresholds opened wide, so a case does
# not wait on how busy the machine is.
ADMISSION_OPENED_DRIVER = r'''
import importlib.util, sys
program_path, *arguments = sys.argv[1:]
spec = importlib.util.spec_from_file_location("run_all_test_suites", program_path)
program = importlib.util.module_from_spec(spec)
sys.argv = [program_path, *arguments]
spec.loader.exec_module(program)
program.TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW = 101
program.TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE = -1
sys.exit(program.main(arguments))
'''
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


def linux_only_cases_run_here(cases):
    """True on Linux; elsewhere prints why the cases are skipped and returns False.

    Every case that builds or inspects a test sandbox, runs bwrap or reads /proc goes
    through this, since only Linux has them. The check at the end of this file runs this
    file and the other runner test files as if on a Mac, and fails a case that does not.
    """
    if sys.platform.startswith("linux"):
        return True
    print(f"SKIP  {cases}: test sandboxes, bwrap and /proc exist only on Linux")
    return False


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
        [sys.executable, "-c", ADMISSION_OPENED_DRIVER, str(RUNNER_PATH), "--checkout", str(repository),
         "--log-dir", str(scratch / "logs"),
         "--lock-file", str(scratch / "run.lock"),
         "--recorded-inputs-directory", str(scratch / "recordings")],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL, check=False)
    if linux_only_cases_run_here("the broken-bwrap refusal"):
        check("on Linux, a bwrap that fails to start stops the run with exit 2 before any suite runs",
              completed.returncode == runner.EXIT_COULD_NOT_RUN
              and "signal sandbox could not start" in completed.stderr
              and "No permissions" in completed.stderr
              and not ran_marker.exists(),
              (completed.returncode, completed.stderr[-600:]))

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
        [sys.executable, "-c", ADMISSION_OPENED_DRIVER, str(RUNNER_PATH), "--checkout", str(repository),
         "--log-dir", str(scratch / "logs"),
         "--lock-file", str(scratch / "run.lock"),
         "--recorded-inputs-directory", str(scratch / "recordings")],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL, check=False)
    report_file = scratch / "logs" / runner.REPORT_FILE_NAME
    report = report_file.read_text() if report_file.exists() else ""
    return completed, report


OUTSIDE_SUITE = "scripts/mac-window-opened-for-ned-box-forced-command-test.py"

if linux_only_cases_run_here("the report's sandbox lines"):
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
        # bash, because dash cannot redirect to a descriptor numbered 10 or more.
        (fake_bin / "bwrap").write_text(
            "#!/bin/bash\n"
            "status_fd=\n"
            "while [ $# -gt 0 ]; do\n"
            "  case \"$1\" in\n"
            "    --dev-bind|--bind|--ro-bind|--ro-bind-try|--setenv) shift 3 ;;\n"
            "    --proc|--dev|--tmpfs|--overlay-src|--tmp-overlay|--unsetenv) shift 2 ;;\n"
            "    --json-status-fd) status_fd=$2; shift 2 ;;\n"
            "    --unshare-pid|--unshare-net|--unshare-ipc|--die-with-parent) shift ;;\n"
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
    # A checkout, since a test sandbox keeps the checkout's git directory read-only.
    subprocess.run(["git", "init", "-q"], cwd=scratch, check=True)
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


# --- Covers over listening sockets that vanish or cannot be reached -----------

def proc_net_unix_listing(paths):
    """A /proc/net/unix text listing each path as a listening stream socket."""
    rows = ["Num       RefCount Protocol Flags    Type St Inode Path"]
    rows += [f"0000000000000000: 00000002 00000000 00010000 0001 01 {100 + number} {path}"
             for number, path in enumerate(paths)]
    return "\n".join(rows) + "\n"


if linux_only_cases_run_here("the covers over listening sockets, and a test sandbox that cannot start"):
    with tempfile.TemporaryDirectory(dir=pathlib.Path.home()) as home_scratch_name, \
            tempfile.TemporaryDirectory() as scratch_name:
        home_scratch = pathlib.Path(home_scratch_name)
        scratch = pathlib.Path(scratch_name)
        listening = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        reachable = str(home_scratch / "listening.sock")
        listening.bind(reachable)
        listening.listen()
        vanished = str(home_scratch / "vanished.sock")
        # /root is closed to every account but root, so this program cannot lstat inside it. A
        # directory this account makes with mode 000 would not do: the scan leaves out every
        # directory this account can write in, as hidden.
        unreachable_path = "/root/nedschorus-run-all-test-suites-test.sock"
        listing = scratch / "unix"
        listing.write_text(proc_net_unix_listing([reachable, vanished, unreachable_path]))
        unreachable = []
        try:
            found = runner.listening_unix_sockets_the_test_sandbox_would_show(str(listing), unreachable)
        finally:
            listening.close()
        check("a listening socket this program can reach is covered", reachable in found, found)
        check("a listening socket gone before the scan's lstat is left out of the covers, "
              "so bwrap is not asked to bind over a missing path", vanished not in found, found)
        if os.geteuid() != 0:
            check("a listening socket this program cannot reach is left out of the covers, "
                  "so bwrap's start does not fail on it", unreachable_path not in found, found)
            check("a listening socket this program cannot reach is named as uncovered, with its error",
                  any(entry.startswith(unreachable_path + " (") for entry in unreachable), unreachable)
            line = runner.uncovered_listening_sockets_report_line_or_none(str(listing))
            check("the run's report names a listening socket left uncovered because it cannot be "
                  "reached, and says the run goes on",
                  line is not None and unreachable_path in line and vanished not in line
                  and "the run goes on" in line, line)
        else:
            print("SKIP  an unreachable socket: root can reach every path")
        listing.write_text(proc_net_unix_listing([vanished]))
        check("with no unreachable listening socket, the report has no uncovered-sockets line",
              runner.uncovered_listening_sockets_report_line_or_none(str(listing)) is None)

    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = pathlib.Path(scratch_name)
        subprocess.run(["git", "init", "-q"], cwd=scratch, check=True)
        (scratch / "plain-test.sh").write_text("echo ran\n")
        fake_bin = scratch / "bin"
        fake_bin.mkdir()
        # Fails as bwrap does when a path it must bind over vanished before it started.
        (fake_bin / "bwrap").write_text(
            "#!/bin/sh\necho \"bwrap: Can't create file at /var/gone.sock: Read-only file system\" >&2\n"
            "exit 1\n")
        (fake_bin / "bwrap").chmod(0o755)
        failed = runner.run_one_suite(scratch, sys.executable, "plain-test.sh", scratch,
                                      sandbox_prefix=(str(fake_bin / "bwrap"),),
                                      note_suite_process=lambda *arguments, **options: None)
        text = failed["log"].read_text()
        check("a suite whose test sandbox could not start fails, with bwrap's message kept in its log",
              failed["exit"] != 0 and "Can't create file at /var/gone.sock" in text, text)
        check("a suite whose test sandbox could not start says so plainly in its log, and what to do",
              "the suite did not start: bwrap could not build its test sandbox" in text
              and "run the suite again" in text, text)


# --- Hiding by default: fixed directories ----------------------------------------

# Written out here, not read from the runner, so a runner that stops hiding one fails a case:
# /mnt holds the backup drive's snapshots of the home directory, credentials included.
if linux_only_cases_run_here("the fixed directories every test sandbox hides"):
    fixed_pairs = list(zip(runner.SIGNAL_SANDBOX_BWRAP_ARGUMENTS, runner.SIGNAL_SANDBOX_BWRAP_ARGUMENTS[1:]))
    for directory in ("/mnt", "/media", "/var/snap"):
        check(f"every test sandbox hides {directory} whole with an empty tmpfs",
              ("--tmpfs", directory) in fixed_pairs, runner.SIGNAL_SANDBOX_BWRAP_ARGUMENTS)

# --- Hiding by default: writable directories, and sockets left visible ---------

if linux_only_cases_run_here("the scan for writable directories"):
    scan = runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox
    scan.cache_clear()
    scanned = scan()
    check("the scan finds /var/tmp, which every account can create files in, to hide it",
          "/var/tmp" in scanned, scanned)
    check("the scan walks none of the directories the sandbox already makes private or empty",
          not any(path == top or path.startswith(top + "/")
                  for path in scanned for top in (
                      *runner.TEST_SANDBOX_PRIVATE_DIRECTORY_PATHS_NOT_SCANNED_FOR_WRITABLE_DIRECTORIES,
                      runner.REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX,
                      *runner.TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS)), scanned)
    # A change that stops hiding one of them must not make the scan walk it: /mnt holds the
    # backup drive, which a walk would crawl for as long as its timeout allows.
    walked = []
    real_run = runner.subprocess.run
    original_fixed = runner.TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS
    runner.TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS = {
        path: reason for path, reason in original_fixed.items() if path != "/mnt"}
    runner.subprocess.run = lambda command, *arguments, **options: (
        walked.append(command), subprocess.CompletedProcess(command, 0, "", ""))[1]
    scan.cache_clear()
    try:
        scan()
        raised = None
    except runner.SignalSandboxCouldNotStart as error:
        raised = str(error)
    finally:
        runner.subprocess.run = real_run
        runner.TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS = original_fixed
        scan.cache_clear()
    check("when /mnt would no longer be hidden whole, the scan refuses without walking it, "
          "and names it", raised is not None and "/mnt" in raised and walked == [],
          (raised, walked))
    for label, stand_in in (
            ("find exits 2", lambda *arguments, **options: subprocess.CompletedProcess(
                arguments[0], 2, "", "find: bad expression")),
            ("find cannot start", lambda *arguments, **options: (_ for _ in ()).throw(
                FileNotFoundError("find")))):
        scan.cache_clear()
        runner.subprocess.run = stand_in
        try:
            scan()
            raised = None
        except runner.SignalSandboxCouldNotStart as error:
            raised = str(error)
        finally:
            runner.subprocess.run = real_run
        check(f"when the scan for writable directories fails ({label}), the sandbox is not "
              f"built", raised is not None and "scan for directories" in raised, raised)
    scan.cache_clear()

home_hidden = (runner.REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX,)


def stub_interpreter(path, loaded, status=0):
    """A stand-in interpreter that reports the given loaded paths as a real one would."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # printf's format turns each \\0 into the NUL a real interpreter's answer holds.
    path.write_text("#!/bin/sh\nprintf " + shlex.quote("\\0".join(loaded)) + f"\nexit {status}\n")
    path.chmod(0o755)
    return str(path)


if linux_only_cases_run_here("what a suite's test sandbox shows and hides"):
    with tempfile.TemporaryDirectory(
            dir=runner.REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX) as home_name:
        home_scratch = pathlib.Path(home_name).resolve()
        shown = runner.interpreter_directories_shown_read_only_in_test_sandbox
        shown.cache_clear()
        environment_root = home_scratch / "venv"
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(environment_root)],
                       check=True)
        venv_shown = shown(str(environment_root / "bin" / "python3"), home_hidden)
        venv_site = subprocess.run(
            [str(environment_root / "bin" / "python3"), "-I", "-c",
             "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            capture_output=True, text=True, check=True).stdout.strip()
        check("an interpreter in a virtual environment in the hidden home directory has the "
              "environment's site-packages and pyvenv.cfg shown, not the whole environment",
              any(venv_site == path or venv_site.startswith(path + "/") for path in venv_shown)
              and str(environment_root / "pyvenv.cfg") in venv_shown
              and str(environment_root) not in venv_shown, venv_shown)
        # An installation whose prefix is a stand-in ~/.local, which also holds the keyrings.
        local = home_scratch / "local"
        for directory in ("bin", "lib/python3.99/lib-dynload", "lib/python3.99/site-packages",
                          "share/keyrings"):
            (local / directory).mkdir(parents=True)
        (local / "share" / "keyrings" / "login.keyring").write_text("secret")
        stdlib = str(local / "lib" / "python3.99")
        site = str(local / "lib" / "python3.99" / "site-packages")
        local_python = local / "bin" / "python3"
        local_loaded = [str(local_python), str(local_python), stdlib,
                        str(local / "lib" / "python3.99" / "lib-dynload"), site, site]
        local_shown = shown(stub_interpreter(local_python, local_loaded), home_hidden)
        check("an interpreter whose prefix is ~/.local has its standard library and its "
              "executable shown, and nothing else of the prefix, so ~/.local/share/keyrings stays "
              "hidden",
              stdlib in local_shown and str(local_python) in local_shown
              and not any(str(local / "share") == path or str(local / "share").startswith(path + "/")
                          or path == str(local) for path in local_shown), local_shown)
        holding = stub_interpreter(home_scratch / "odd" / "python3",
                                   [str(home_scratch / "odd" / "python3")] * 2
                                   + [runner.REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX] * 4)
        try:
            shown(holding, home_hidden)
            raised = None
        except runner.SignalSandboxCouldNotStart as error:
            raised = str(error)
        check("an interpreter that loads the hidden home directory itself stops the sandbox from "
              "being built, since showing it would show the whole home directory",
              raised is not None and "hides whole" in raised, raised)
        broken = stub_interpreter(home_scratch / "broken" / "python3", ["/x"] * 6, status=3)
        try:
            shown(broken, home_hidden)
            raised = None
        except runner.SignalSandboxCouldNotStart as error:
            raised = str(error)
        check("an interpreter that cannot report what it loads stops the sandbox from being "
              "built, naming the interpreter", raised is not None and broken in raised, raised)
        launcher = home_scratch / "launcher" / "scripts" / "run-suite-in-signal-sandbox.py"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("")
        original_hidden = runner.directories_hidden_whole_in_test_sandbox
        runner.directories_hidden_whole_in_test_sandbox = lambda: home_hidden
        try:
            launch = runner.paths_one_suite_launch_needs_shown_read_only_in_test_sandbox(
                ["/usr/bin/python3"], [launcher])
        finally:
            runner.directories_hidden_whole_in_test_sandbox = original_hidden
        check("a program file run inside the sandbox from the hidden home directory, such as the "
              "launcher that checks the sandbox from inside, has its directory shown",
              launch == [os.path.realpath(launcher.parent)], launch)
        runner.directories_hidden_whole_in_test_sandbox = lambda: home_hidden
        try:
            launch_in_checkout = runner.paths_one_suite_launch_needs_shown_read_only_in_test_sandbox(
                ["/usr/bin/python3"], [launcher], checkout=launcher.parent.parent)
        finally:
            runner.directories_hidden_whole_in_test_sandbox = original_hidden
        check("a program file inside the checkout under test has nothing shown, so no read-only "
              "directory covers the checkout's writable copy",
              launch_in_checkout == [], launch_in_checkout)
        shown.cache_clear()
    with tempfile.TemporaryDirectory() as path_name:
        on_path = pathlib.Path(path_name) / "bin"
        on_path.mkdir()
        (on_path / "python-on-path-only").symlink_to(sys.executable)
        elsewhere = pathlib.Path(path_name) / "elsewhere"
        elsewhere.mkdir()
        saved_path, saved_directory = os.environ.get("PATH", ""), os.getcwd()
        os.environ["PATH"] = f"{on_path}{os.pathsep}{saved_path}"
        os.chdir(elsewhere)
        try:
            runner.interpreter_directories_shown_read_only_in_test_sandbox.cache_clear()
            runner.interpreter_directories_shown_read_only_in_test_sandbox(
                "python-on-path-only", ("/no-directory-is-hidden-for-this-case",))
            raised = None
        except runner.SignalSandboxCouldNotStart as error:
            raised = str(error)
        finally:
            os.chdir(saved_directory)
            os.environ["PATH"] = saved_path
            runner.interpreter_directories_shown_read_only_in_test_sandbox.cache_clear()
        check("an interpreter given by a bare name, as --python python3, is the one PATH finds, "
              "not a file of that name in the current directory", raised is None, raised)
    if os.path.exists("/usr/bin/python3"):
        check("an interpreter outside the home directory needs nothing shown",
              runner.interpreter_directories_shown_read_only_in_test_sandbox(
                  "/usr/bin/python3", home_hidden) == [])

    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = pathlib.Path(scratch_name)
        subprocess.run(["git", "init", "-q"], cwd=scratch, check=True)
        original_scan = runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox
        original_listening = runner.listening_unix_sockets_the_test_sandbox_would_show
        runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox = (
            lambda: ("/var/crash-for-this-case",))
        runner.listening_unix_sockets_the_test_sandbox_would_show = (
            lambda *arguments, **options: ["/var/lib/a-service/listening.sock", "/var/direct.sock"])
        try:
            arguments = runner.bwrap_arguments_for_one_suites_test_sandbox(scratch)
        finally:
            runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox = original_scan
            runner.listening_unix_sockets_the_test_sandbox_would_show = original_listening
        pairs = list(zip(arguments, arguments[1:]))
        check("each directory this account can create files in is an empty tmpfs in the sandbox",
              ("--tmpfs", "/var/crash-for-this-case") in pairs, arguments)
        check("a listening socket left visible is hidden with its whole directory, so the "
              "service making it again there does not show it",
              ("--tmpfs", "/var/lib/a-service") in pairs, arguments)
        check("a listening socket directly in a system directory is covered by an empty file, "
              "and the system directory is not hidden",
              "/var/direct.sock" in arguments and ("--tmpfs", "/var") not in pairs, arguments)

        # A checkout inside a directory the scan hides, as `--checkout /var/tmp/repo` puts it,
        # with a read-only path inside the checkout and a writable one inside the read-only one.
        real_scratch = os.path.realpath(scratch)
        hidden_parent = os.path.dirname(real_scratch)
        read_only_inside = scratch / "recorder"
        writable_inside = read_only_inside / "record"
        writable_inside.mkdir(parents=True)
        runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox = (
            lambda: (hidden_parent,))
        runner.listening_unix_sockets_the_test_sandbox_would_show = (
            lambda *arguments, **options: [])
        try:
            arguments = runner.bwrap_arguments_for_one_suites_test_sandbox(
                scratch, [writable_inside], read_only_paths=[read_only_inside])
        finally:
            runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox = original_scan
            runner.listening_unix_sockets_the_test_sandbox_would_show = original_listening
        pairs = list(zip(arguments, arguments[1:]))

        def position(pair):
            return pairs.index(pair) if pair in pairs else None

        cover = position(("--tmpfs", hidden_parent))
        checkout_bind = position(("--tmp-overlay", real_scratch))
        read_only_bind = position(("--ro-bind", os.path.realpath(read_only_inside)))
        writable_bind = position(("--bind", os.path.realpath(writable_inside)))
        check("a directory the scan hides is covered before the checkout inside it is bound, so "
              "the cover does not hide the checkout",
              None not in (cover, checkout_bind) and cover < checkout_bind, arguments)
        check("the checkout under test is a copy-on-write overlay of itself, not bound writable, "
              "so nothing a suite writes in it survives the suite",
              checkout_bind is not None
              and pairs[checkout_bind - 2] == ("--overlay-src", real_scratch)
              and ("--bind", real_scratch) not in pairs, arguments)
        check("a read-only path inside the checkout's copy-on-write overlay is bound after the "
              "overlay, so it stays read-only",
              None not in (checkout_bind, read_only_bind) and checkout_bind < read_only_bind,
              arguments)
        check("a writable path inside a read-only one is bound after it, so it stays writable",
              None not in (read_only_bind, writable_bind) and read_only_bind < writable_bind,
              arguments)


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
elif sys.platform == "darwin" and not os.path.isfile(runner.SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC):
    print(f"SKIP  the end-to-end sandbox-exec case: {runner.SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC} "
          f"is not on this Mac")
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
elif not linux_only_cases_run_here("sandbox isolation"):
    pass
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

# --- Off Linux, every Linux-only case of the runner's test files is skipped -------

# Loaded first in a runner test file's own process, it makes that process see a Mac:
# sys.platform is darwin, and the paths a Mac lacks are missing. The programs a case
# starts run unchanged, since they are not the case. It writes "loaded" to the record
# file, then each /proc path the test file itself opens and each bwrap the process starts.
AS_IF_ON_A_MAC_SITECUSTOMIZE = r"""
import os, sys, sysconfig, traceback
_here = os.path.dirname(os.path.abspath(__file__))
# Off sys.path too, or a sitecustomize this one runs, such as the runner's input recorder,
# finds this one again when it runs the sitecustomize it shadows.
sys.path[:] = [entry for entry in sys.path if os.path.abspath(entry or ".") != _here]
os.environ["PYTHONPATH"] = os.pathsep.join(
    entry for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep)
    if entry and os.path.abspath(entry) != _here)
_record = os.environ.pop("AS_IF_ON_A_MAC_RECORD_FILE")
_standard_library = tuple({sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["platstdlib"]})
_MISSING_ON_A_MAC = ("/proc", "/mnt", "/media", "/var/snap", "/run", "/root")
sys.platform = "darwin"


def _note(line):
    with open(_record, "a") as record:
        record.write(line + "\n")


def _missing(path):
    try:
        path = os.fsdecode(os.fspath(path))
    except TypeError:
        return False
    return any(path == top or path.startswith(top + "/") for top in _MISSING_ON_A_MAC)


def _opener_is_the_test_file():
    for frame in reversed(traceback.extract_stack()[:-3]):
        if frame.filename == __file__ or frame.filename.startswith(_standard_library):
            continue
        return frame.filename.endswith("-test.py"), f"{os.path.basename(frame.filename)}:{frame.lineno}"
    return False, "?"


def _hiding(function):
    def hidden(path, *arguments, **options):
        if _missing(path):
            raise FileNotFoundError(2, "No such file or directory", path)
        return function(path, *arguments, **options)
    return hidden


os.stat, os.lstat = _hiding(os.stat), _hiding(os.lstat)


def _audit(event, arguments):
    if event in ("open", "os.listdir", "os.scandir") and arguments and arguments[0] is not None \
            and _missing(arguments[0]):
        path = os.fsdecode(os.fspath(arguments[0]))
        by_test, where = _opener_is_the_test_file()
        if by_test and path.startswith("/proc"):
            _note(f"{where} opened {path}")
        raise FileNotFoundError(2, "No such file or directory", path)
    if event == "subprocess.Popen" and arguments:
        program = arguments[0] if arguments[0] else (list(arguments[1] or []) or [""])[0]
        program = os.path.realpath(os.fsdecode(os.fspath(program)))
        if os.path.basename(program) == "bwrap" and program.startswith(("/usr/", "/bin/")):
            _note(f"{_opener_is_the_test_file()[1]} started {program}")
            raise FileNotFoundError(2, "No such file or directory", program)


_note("loaded")
sys.addaudithook(_audit)


def _run_the_shadowed_sitecustomize():
    import importlib.machinery, importlib.util
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", sys.path)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


_run_the_shadowed_sitecustomize()
"""
# Every runner test file whose cases run in its own process. run-all-test-suites-test.py
# is not here: its cases start the runner as a program, which this cannot make a Mac's.
RUNNER_TEST_FILES_RUN_AS_IF_ON_A_MAC = (
    "run-all-test-suites-signal-sandbox-test.py",
    "run-all-test-suites-machine-wide-test-suite-admission-test.py",
    "run-suite-in-signal-sandbox-test.py",
    "run-all-test-suites-cleanup-after-killed-runs-real-process-test.py",
    "run-all-test-suites-overlapping-runs-real-process-test.py",
    "run-all-test-suites-test-sandbox-escape-test.py",
)


def run_as_if_on_a_mac(script, stub_directory):
    """Run script with the Mac stand-in loaded; return (exit code, output, record lines)."""
    record = stub_directory / f"{pathlib.Path(script).name}.record"
    record.unlink(missing_ok=True)
    environment = {name: value for name, value in os.environ.items()
                   if name != runner.SIGNAL_SANDBOX_INSIDE_VARIABLE}
    environment["PYTHONPATH"] = os.pathsep.join(
        entry for entry in (str(stub_directory), environment.get("PYTHONPATH", "")) if entry)
    environment["AS_IF_ON_A_MAC_RECORD_FILE"] = str(record)
    completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                               env=environment, stdin=subprocess.DEVNULL, timeout=900,
                               check=False)
    lines = record.read_text().splitlines() if record.exists() else []
    return completed.returncode, completed.stdout + completed.stderr, lines


if linux_only_cases_run_here("the run of the runner's test files as if on a Mac"):
    with tempfile.TemporaryDirectory() as stub_name:
        stub_directory = pathlib.Path(stub_name)
        (stub_directory / "sitecustomize.py").write_text(AS_IF_ON_A_MAC_SITECUSTOMIZE)
        # The control: a test file that does what a Linux-only case does is caught.
        probe = stub_directory / "linux-only-probe-test.py"
        probe.write_text(
            "import os, pathlib, subprocess, sys\n"
            "print(sys.platform, os.path.isdir('/mnt'))\n"
            "try:\n"
            "    pathlib.Path('/proc/self/stat').read_text()\n"
            "except FileNotFoundError:\n"
            "    print('no /proc')\n"
            "try:\n"
            "    subprocess.run(['/usr/bin/bwrap', '--version'])\n"
            "except FileNotFoundError:\n"
            "    print('no bwrap')\n")
        code, output, lines = run_as_if_on_a_mac(probe, stub_directory)
        check("control: run as if on a Mac, a test file sees darwin, no /mnt, no /proc and no "
              "bwrap, and its /proc read and its bwrap are recorded",
              output.split() == ["darwin", "False", "no", "/proc", "no", "bwrap"]
              and lines[:1] == ["loaded"]
              and any("linux-only-probe-test.py" in line and "/proc/self/stat" in line
                      for line in lines)
              and any(line.endswith("started /usr/bin/bwrap") for line in lines),
              (output, lines))
        for name in RUNNER_TEST_FILES_RUN_AS_IF_ON_A_MAC:
            code, output, lines = run_as_if_on_a_mac(SCRIPTS_DIR / name, stub_directory)
            failed = [line for line in output.splitlines()
                      if line.startswith("FAIL") or line.startswith("Traceback")]
            check(f"run as if on a Mac, {name} passes, and none of its cases reads /proc or "
                  f"starts bwrap",
                  code == 0 and not failed and lines == ["loaded"],
                  (code, failed, lines[1:] if lines[:1] == ["loaded"] else lines,
                   output[-800:] if code else ""))

# --- The refusal naming directories the writable-directory scan never walks ----------
with tempfile.TemporaryDirectory() as scratch_name:
    never_walked = [os.path.join(scratch_name, name) for name in ("first", "second")]
    for path in never_walked:
        os.mkdir(path)
    original_never_walked = runner.TEST_SANDBOX_DIRECTORIES_THE_WRITABLE_DIRECTORY_SCAN_NEVER_WALKS
    for named, pronoun in ((never_walked[:1], "what it holds"), (never_walked, "what they hold")):
        runner.TEST_SANDBOX_DIRECTORIES_THE_WRITABLE_DIRECTORY_SCAN_NEVER_WALKS = tuple(named)
        runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox.cache_clear()
        try:
            runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox()
            refusal = None
        except runner.SignalSandboxCouldNotStart as error:
            refusal = str(error)
        finally:
            runner.TEST_SANDBOX_DIRECTORIES_THE_WRITABLE_DIRECTORY_SCAN_NEVER_WALKS = \
                original_never_walked
            runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox.cache_clear()
        check(f"the refusal naming {len(named)} directory(ies) the scan never walks says "
              f"\"{pronoun}\"",
              refusal is not None and all(path in refusal for path in named)
              and f"so {pronoun} would show inside it" in refusal, refusal)

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
