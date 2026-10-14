#!/usr/bin/env python3
"""Tests that a suite inside its test sandbox cannot escape it.

The environment is built by scripts/run-all-test-suites.py's own code, exactly as
for a suite, and a probe inside it tries every escape. Each target is one this
file made for the purpose: a file in the real home directory, a tmux server on a
socket of its own, a listening socket in the session's runtime directory, a
sleeper process, a scratch repository. If a protection were missing, the worst a
probe can do is change those targets, and this file removes them afterwards.
The real credential files are only measured, never printed.

bwrap cannot start inside bwrap, so the runner runs this suite outside its
sandbox (SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX); run anywhere bwrap cannot
start, it prints SKIP.

Run: python3 scripts/run-all-test-suites-test-sandbox-escape-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import pathlib
import shutil
import socket
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

RUNNER_PATH = pathlib.Path(__file__).resolve().parent / "run-all-test-suites.py"

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

# Listed here as well as in the runner, so dropping one from the runner's list fails a case.
SOCKET_VARIABLES_THAT_MUST_BE_UNSET = (
    "TMUX", "TMUX_PANE", "DBUS_SESSION_BUS_ADDRESS", "SSH_AUTH_SOCK",
    "CLAUDE_CODE_MESSAGING_SOCKET")
CREDENTIAL_FILES_THAT_MUST_BE_HIDDEN = (
    ".config/nedschorus/*.token", ".claude/.credentials.json", ".codex/auth.json")

# Runs inside the environment. Each attempt prints one JSON line: what it tried and
# whether it worked. It writes only to the paths it is given.
PROBE_SOURCE = r'''
import json, os, signal, socket, subprocess, sys
targets = json.loads(os.environ["ESCAPE_TEST_TARGETS"])
def report(attempt, worked, detail=""):
    print(json.dumps({"attempt": attempt, "worked": bool(worked), "detail": str(detail)}), flush=True)
def attempt(name, action):
    try:
        result = action()
    except BaseException as error:
        report(name, False, repr(error))
    else:
        report(name, True if result is None else result, "")
def write(path, text="probe"):
    with open(path, "w") as handle:
        handle.write(text)
canary = targets["home_canary"]
attempt("write the home canary", lambda: write(canary, "changed by the probe"))
attempt("chmod the home canary", lambda: os.chmod(canary, 0o600))
attempt("rename the home canary", lambda: os.rename(canary, canary + ".renamed"))
attempt("delete the home canary", lambda: os.unlink(canary + ".renamed")
        if os.path.exists(canary + ".renamed") else os.unlink(canary))
attempt("create a file in the home directory", lambda: write(targets["home_new_file"]))
for path in targets["credential_files"]:
    def read(path=path):
        with open(path, "rb") as handle:
            return len(handle.read()) > 0
    attempt(f"read credential file {path}", read)
for path in targets["outside_files"]:
    attempt(f"write {path}", lambda path=path: write(path))
def tmux_has_session():
    done = subprocess.run(["tmux", "-L", targets["tmux_socket_name"], "has-session"],
                          capture_output=True, text=True)
    return done.returncode == 0
attempt("reach the tmux server by name", tmux_has_session)
def connect(path):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.connect(path)
    finally:
        connection.close()
attempt("connect to the tmux server's socket", lambda: connect(targets["tmux_socket_path"]))
attempt("connect to the runtime directory's socket", lambda: connect(targets["runtime_socket_path"]))
attempt("connect to the session bus", lambda: connect(targets["session_bus_path"]))
def systemd_run():
    done = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "true"],
                          capture_output=True, text=True)
    return done.returncode == 0
attempt("start a process outside with systemd-run --user", systemd_run)
attempt("signal the sleeper outside", lambda: os.kill(targets["sleeper_pid"], signal.SIGTERM))
git_directory = targets["git_directory"]
attempt("write a ref in the repository's git directory",
        lambda: write(os.path.join(git_directory, "refs", "heads", "escaped"), "0" * 40 + "\n"))
def append_config():
    with open(os.path.join(git_directory, "config"), "a") as handle:
        handle.write("[escaped]\n")
attempt("change the repository's git config", append_config)
def git_branch():
    done = subprocess.run(["git", "-C", targets["checkout"], "branch", "escaped-by-git"],
                          capture_output=True, text=True)
    return done.returncode == 0
attempt("create a branch with git", git_branch)
for variable in targets["outside_socket_variables"]:
    report(f"see variable {variable}", variable in os.environ, os.environ.get(variable, ""))
attempt("write in the checkout under test", lambda: write(targets["checkout_file"]))
attempt("write in the log directory", lambda: write(targets["log_file"]))
'''


def bwrap_unavailable_reason():
    if not sys.platform.startswith("linux"):
        return f"{sys.platform} has no test sandbox; it is built with bwrap on Linux"
    if os.environ.get(runner.SIGNAL_SANDBOX_INSIDE_VARIABLE):
        return "this suite is already inside a sandbox, where bwrap cannot start again"
    if shutil.which("bwrap") is None:
        return "bwrap is not on PATH"
    return None


def git(*arguments, cwd):
    done = subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(arguments)} failed in {cwd}: {done.stderr.strip()}")
    return done.stdout


def git_directory_state(git_directory):
    """Every file under the git directory with its size and modification time."""
    state = {}
    for root, _, names in os.walk(git_directory):
        for name in names:
            path = os.path.join(root, name)
            status = os.lstat(path)
            state[os.path.relpath(path, git_directory)] = (status.st_size, status.st_mtime_ns)
    return state


def run_probe(scratch):
    """Build one suite's environment, run the probe in it, and check every target after."""
    sandbox_prefix, unconfined_because = runner.signal_sandbox()
    if not sandbox_prefix:
        print(f"SKIP  every escape case: the runner builds no sandbox here: {unconfined_because}")
        return
    home = pathlib.Path(runner.TEST_SANDBOX_HOME)
    runtime = pathlib.Path(runner.TEST_SANDBOX_RUNTIME_DIRECTORY)
    name = f"run-all-test-suites-escape-test-{os.getpid()}"

    # A checkout whose git directory lies inside it, as in a clone, so the read-only
    # bind of the git directory is all that protects it.
    checkout = scratch / "checkout"
    checkout.mkdir()
    git("init", "-q", cwd=checkout)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty",
        "-m", "start", cwd=checkout)
    git_directory = checkout / ".git"
    log_dir = scratch / "log"
    log_dir.mkdir()

    canary_dir = home / ".cache" / name
    canary_dir.mkdir(parents=True)
    canary = canary_dir / "canary"
    canary.write_text("original")
    canary.chmod(0o644)
    host_tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"{name}-", dir="/tmp"))
    var_tmp_file = pathlib.Path("/var/tmp") / f"{name}-probe"
    dev_shm_file = pathlib.Path("/dev/shm") / f"{name}-probe"
    runtime_file = runtime / f"{name}-probe"
    outside_files = [host_tmp / "probe", var_tmp_file, dev_shm_file, runtime_file,
                     pathlib.Path("/etc") / f"{name}-probe"]

    tmux_environment = {key: value for key, value in os.environ.items()
                        if key not in ("TMUX", "TMUX_PANE", "TMUX_TMPDIR")}
    tmux_started = subprocess.run(["tmux", "-L", name, "new-session", "-d", "sleep", "600"],
                                  env=tmux_environment, capture_output=True, text=True)
    tmux_socket_path = pathlib.Path("/tmp") / f"tmux-{os.getuid()}" / name
    runtime_socket_path = runtime / f"{name}.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(runtime_socket_path))
    listener.listen(1)
    listener.setblocking(False)
    sleeper = subprocess.Popen(["sleep", "600"])
    git_before = git_directory_state(git_directory)
    credential_files = sorted(
        set(runner.test_sandbox_real_credential_files_hidden_from_tests())
        | {str(path) for pattern in CREDENTIAL_FILES_THAT_MUST_BE_HIDDEN
           for path in home.glob(pattern) if path.is_file()})
    socket_variables = sorted(set(runner.TEST_SANDBOX_OUTSIDE_SOCKET_VARIABLES)
                              | set(SOCKET_VARIABLES_THAT_MUST_BE_UNSET))
    nonempty_credentials = [path for path in credential_files if os.path.getsize(path) > 0]

    targets = {
        "home_canary": str(canary),
        "home_new_file": str(canary_dir / "new-file"),
        "credential_files": credential_files,
        "outside_files": [str(path) for path in outside_files],
        "tmux_socket_name": name,
        "tmux_socket_path": str(tmux_socket_path),
        "runtime_socket_path": str(runtime_socket_path),
        "session_bus_path": str(runtime / "bus"),
        "sleeper_pid": sleeper.pid,
        "git_directory": str(git_directory),
        "checkout": str(checkout),
        "outside_socket_variables": socket_variables,
        "checkout_file": str(checkout / "probe-stays"),
        "log_file": str(log_dir / "probe-stays"),
    }
    environment = runner.test_suite_launch_environment_without_git_redirecting_and_agent_session_attendance_variables()
    for variable in socket_variables:
        environment.setdefault(variable, f"/outside/{variable.lower()}")
    environment["ESCAPE_TEST_TARGETS"] = json.dumps(targets)
    command = [*runner.signal_sandbox_prefix_for_suite(sandbox_prefix, checkout, (log_dir,)),
               sys.executable, "-c", PROBE_SOURCE]
    try:
        probe = subprocess.run(command, cwd=str(checkout), env=environment,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=120)
        attempts = {}
        for line in probe.stdout.splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            attempts[record["attempt"]] = record
        check("the probe ran inside the environment and reported",
              probe.returncode == 0 and len(attempts) > 20,
              (probe.returncode, probe.stdout[-800:], probe.stderr[-800:]))

        def blocked(attempt):
            record = attempts.get(attempt)
            return record is not None and not record["worked"], record

        check("precondition: the tmux server of this test started",
              tmux_started.returncode == 0, tmux_started.stderr)
        check("precondition: at least one real credential file exists and is not empty",
              bool(nonempty_credentials), credential_files)

        # Suites write in the home directory, so inside it must take the writes.
        for attempt in ("write the home canary", "chmod the home canary",
                        "rename the home canary", "delete the home canary",
                        "create a file in the home directory"):
            record = attempts.get(attempt)
            check(f"inside, the home directory takes the write: {attempt}",
                  record is not None and record["worked"], record)
        check("outside afterwards, the home canary is unchanged: content, mode and name",
              canary.is_file() and canary.read_text() == "original"
              and (canary.stat().st_mode & 0o777) == 0o644
              and not (canary_dir / "canary.renamed").exists(),
              sorted(path.name for path in canary_dir.iterdir()))
        check("outside afterwards, a file created in the home directory is gone",
              not (canary_dir / "new-file").exists())
        for path in credential_files:
            ok, record = blocked(f"read credential file {path}")
            check(f"a credential file reads as empty or not at all: {path}", ok, record)
        for path in outside_files:
            check(f"outside afterwards, nothing was written at {path}", not path.exists())
        for attempt in ("reach the tmux server by name", "connect to the tmux server's socket",
                        "connect to the runtime directory's socket",
                        "connect to the session bus",
                        "start a process outside with systemd-run --user",
                        "write a ref in the repository's git directory",
                        "change the repository's git config", "create a branch with git"):
            ok, record = blocked(attempt)
            check(f"inside, this fails: {attempt}", ok, record)
        try:
            accepted = listener.accept()
        except BlockingIOError:
            accepted = None
        check("outside afterwards, no connection reached the runtime directory's socket",
              accepted is None)
        check("outside afterwards, the sleeper outside is still running",
              sleeper.poll() is None, sleeper.returncode)
        check("outside afterwards, the repository's git directory is unchanged",
              git_directory_state(git_directory) == git_before)
        for variable in socket_variables:
            ok, record = blocked(f"see variable {variable}")
            check(f"inside, the variable naming a socket outside is unset: {variable}", ok, record)
        # A suite allowed to write the git directory gets a throwaway copy of it.
        git_writer = next(iter(runner.SUITES_GIVEN_A_THROWAWAY_COPY_OF_THE_REPOSITORY_GIT_DIRECTORY))
        written = subprocess.run(
            [*runner.signal_sandbox_prefix_for_suite(sandbox_prefix, checkout, (log_dir,),
                                                     suite=git_writer),
             "git", "-C", str(checkout), "branch", "escaped-by-git"],
            cwd=str(checkout), env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120)
        check("inside, a suite given a copy of the git directory can create a branch",
              written.returncode == 0, written.stderr)
        check("outside afterwards, that branch is not in the repository's git directory",
              git_directory_state(git_directory) == git_before)
        check("outside afterwards, a write in the checkout under test stays",
              (checkout / "probe-stays").is_file())
        check("outside afterwards, a write in the log directory stays",
              (log_dir / "probe-stays").is_file())
    finally:
        sleeper.kill()
        sleeper.wait()
        listener.close()
        runtime_socket_path.unlink(missing_ok=True)
        subprocess.run(["tmux", "-L", name, "kill-server"], env=tmux_environment,
                       capture_output=True)
        shutil.rmtree(canary_dir, ignore_errors=True)
        shutil.rmtree(host_tmp, ignore_errors=True)
        for path in outside_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


unavailable = bwrap_unavailable_reason()
if unavailable:
    print(f"SKIP  every escape case: {unavailable}")
else:
    with tempfile.TemporaryDirectory() as scratch_name:
        run_probe(pathlib.Path(scratch_name))

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
