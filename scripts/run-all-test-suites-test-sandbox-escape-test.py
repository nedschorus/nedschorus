#!/usr/bin/env python3
"""Tests that a suite inside its test sandbox cannot escape it.

A probe is run as a suite by scripts/run-all-test-suites.py's own run_one_suite,
the path every suite takes: in a cgroup scope at low priority, with the input
recorder, in a checkout that is a linked worktree, as merge-lane-2's head test
runs and mutation testing use. The probe tries every escape. Each target is one
this file made for the purpose: a file in the real home directory, a tmux server
on a socket of its own, a listening socket in the session's runtime directory, a
sleeper process, a scratch repository. If a protection were missing, the worst a
probe can do is change those targets, and this file removes them afterwards. The
real credential files are only measured, never printed, and the machine's real
listening sockets only connected to and closed.

The lists of what must be hidden are written out here, not read from the
runner, so dropping an entry from one of the runner's lists fails a case.

bwrap cannot start inside bwrap, so the runner runs this suite outside its
sandbox (SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX); run anywhere bwrap cannot
start, it prints SKIP.

Run: python3 scripts/run-all-test-suites-test-sandbox-escape-test.py   (exit 0 = all passed)
"""

import contextlib
import importlib.util
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

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

SOCKET_VARIABLES_THAT_MUST_BE_UNSET = (
    "TMUX", "TMUX_PANE", "DBUS_SESSION_BUS_ADDRESS", "SSH_AUTH_SOCK",
    "CLAUDE_CODE_MESSAGING_SOCKET", "DISPLAY", "WAYLAND_DISPLAY", "GPG_AGENT_INFO")
CREDENTIAL_VARIABLES_THAT_MUST_BE_UNSET = (
    "GH_TOKEN", "GITHUB_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_MESSAGING_TOKEN",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "NPM_TOKEN",
    "DATABASE_PASSWORD")
# Relative to the home directory, each matched in its own directory.
CREDENTIAL_FILE_PATTERNS_THAT_MUST_BE_HIDDEN = (
    ".config/nedschorus/*.token", ".claude/.credentials.json", ".codex/auth.json*",
    ".config/gh/hosts.yml", ".ssh/id_*", ".git-credentials", ".netrc",
    ".gnupg/private-keys-v1.d/*", ".local/share/keyrings/*", ".steam/*.token",
    ".aws/credentials", ".docker/config.json", "nedsmessenger/secrets/*",
    ".gemini/antigravity-cli/antigravity-oauth-token")
# Sockets through which a process reaches far outside: root through Docker, the system,
# the service manager. The test names each that is listening among those probed.
MACHINE_SOCKETS_NAMED = (
    "/run/docker.sock", "/run/dbus/system_bus_socket", "/run/snapd.socket",
    "/run/systemd/io.systemd.Manager")
# gnome-shell on ned-box serves displays :0 and :1; its authorization cookie lives in the
# runtime directory, which the test sandbox hides.
X11_DISPLAYS_PROBED = (0, 1)
PROBE_SUITE = "escape-probe-test.py"

# Opens an X11 connection with the first cookie it can find, as a program in the session
# would; True only when the display accepts it. Run inside the environment by the probe,
# and outside by this test, to show it works where the cookie can be read.
X11_PROBE_SOURCE = r'''
import glob, os, socket, struct
def x11_cookies():
    paths = [os.environ.get("XAUTHORITY", ""), os.path.expanduser("~/.Xauthority"),
             *glob.glob("/run/user/*/.mutter-Xwaylandauth*"), *glob.glob("/run/user/*/gdm/Xauthority")]
    cookies = []
    for path in paths:
        try:
            data = open(path, "rb").read()
        except OSError:
            continue
        offset = 2
        while offset + 2 <= len(data):
            fields = []
            for _ in range(4):
                length = struct.unpack(">H", data[offset:offset + 2])[0]
                fields.append(data[offset + 2:offset + 2 + length])
                offset += 2 + length
            if fields[2] == b"MIT-MAGIC-COOKIE-1":
                cookies.append(fields[3])
            offset += 2
    return cookies
def x11_display_accepts(display):
    cookies = x11_cookies() or [b""]
    for cookie in cookies:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(3)
        try:
            try:
                connection.connect(f"\0/tmp/.X11-unix/X{display}")
            except OSError:
                connection.connect(f"/tmp/.X11-unix/X{display}")
            name = b"MIT-MAGIC-COOKIE-1" if cookie else b""
            pad = lambda raw: raw + b"\0" * (-len(raw) % 4)
            connection.sendall(b"l\0" + struct.pack("<HHHH", 11, 0, len(name), len(cookie))
                               + b"\0\0" + pad(name) + pad(cookie))
            if connection.recv(1) == b"\x01":
                return True
        finally:
            connection.close()
    return False
'''

# Runs inside the environment as a suite. Each attempt prints one JSON line: what it
# tried and whether it worked. It writes only to the paths it is given.
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
def read_canary():
    with open(canary) as handle:
        return handle.read() == "original"
attempt("read the home canary", read_canary)
attempt("chmod the home canary", lambda: os.chmod(canary, 0o600))
attempt("rename the home canary", lambda: os.rename(canary, canary + ".renamed"))
attempt("delete the home canary", lambda: os.unlink(canary))
os.makedirs(os.path.dirname(canary), exist_ok=True)
attempt("write the home canary", lambda: write(canary, "changed by the probe"))
attempt("create a file in the home directory", lambda: write(targets["home_new_file"]))
for directory in targets["writable_directories"]:
    attempt(f"create a file in {directory}",
            lambda directory=directory: write(os.path.join(directory, targets["probe_file_name"])))
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
def connect(path, kind=socket.SOCK_STREAM):
    connection = socket.socket(socket.AF_UNIX, kind)
    connection.settimeout(2)
    try:
        connection.connect(path)
    finally:
        connection.close()
attempt("connect to the tmux server's socket", lambda: connect(targets["tmux_socket_path"]))
attempt("connect to the runtime directory's socket", lambda: connect(targets["runtime_socket_path"]))
attempt("connect to the session bus", lambda: connect(targets["session_bus_path"]))
for path, kind in targets["machine_sockets"]:
    address = "\0" + path[1:] if path.startswith("@") else path
    attempt(f"connect to the machine's listening socket {path}",
            lambda address=address, kind=kind: connect(address, kind))
def systemd_run():
    done = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "true"],
                          capture_output=True, text=True)
    return done.returncode == 0
attempt("start a process outside with systemd-run --user", systemd_run)
def connect_tcp():
    connection = socket.create_connection(("127.0.0.1", targets["tcp_port"]), timeout=3)
    connection.close()
attempt("connect to a localhost TCP port outside", connect_tcp)
attempt("connect to an abstract Unix socket outside",
        lambda: connect("\0" + targets["abstract_socket_name"]))
for display in targets["x11_displays"]:
    attempt(f"open an X11 connection to display :{display}",
            lambda display=display: x11_display_accepts(display))
attempt("signal the sleeper outside", lambda: os.kill(targets["sleeper_pid"], signal.SIGTERM))
def system_v_message_queue():
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    queue = libc.msgget(targets["system_v_key"], 0)
    if queue < 0:
        raise OSError(ctypes.get_errno(), "msgget")
attempt("reach a System V message queue outside", system_v_message_queue)
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
# A worktree's .git file names the git directory that later git commands in it use,
# outside the sandbox too; pointed at one with a filter, git would run that filter.
fake = os.path.join(targets["checkout"], "fake-git-directory")
def point_git_file_elsewhere():
    subprocess.run(["git", "init", "-q", "--bare", fake], capture_output=True)
    with open(os.path.join(fake, "config"), "a") as handle:
        handle.write(f"[filter \"escape\"]\n\tclean = touch {targets['filter_marker']}; cat\n")
    write(os.path.join(targets["checkout"], ".gitattributes"), "* filter=escape\n")
    write(os.path.join(targets["checkout"], ".git"), f"gitdir: {fake}\n")
attempt("point the worktree's .git file at another git directory", point_git_file_elsewhere)
for variable in targets["outside_socket_variables"] + targets["credential_variables"]:
    report(f"see variable {variable}", variable in os.environ, "set" if variable in os.environ else "")
attempt("change the input recorder's sitecustomize.py",
        lambda: write(targets["recorder_sitecustomize"], "print('planted')\n"))
for name, path in targets["runner_written_paths"].items():
    def plant(path=path):
        if os.path.lexists(path):
            os.unlink(path)
        os.symlink(targets["symlink_target"], path)
    attempt(f"put a symbolic link where the runner writes {name}", plant)
def plant_in_strace_directory():
    os.symlink(targets["symlink_target"], os.path.join(targets["strace_directory"], "trace.planted-link"))
    os.mkfifo(os.path.join(targets["strace_directory"], "trace.planted-pipe"))
if targets["strace_directory"]:
    attempt("put a link and a named pipe among the strace traces", plant_in_strace_directory)
attempt("write in the run's log directory", lambda: write(targets["log_file"]))
attempt("write in the checkout under test", lambda: write(targets["checkout_file"]))
def append_input_record():
    with open(targets["hook_log"], "a") as handle:
        handle.write("escape-test\tthe probe's own line\n")
attempt("write the suite's own input record", append_input_record)
# Sockets this test makes outside only once the probe has started, in /var/tmp and in the
# home directory: what a process outside makes later must not show inside either.
write(targets["late_sockets_ready"], "the probe is waiting")
import time
deadline = time.monotonic() + 60
while not os.path.exists(targets["late_sockets_made"]) and time.monotonic() < deadline:
    time.sleep(0.1)
report("the late sockets were made outside", os.path.exists(targets["late_sockets_made"]))
for path in targets["late_sockets"]:
    attempt(f"connect to a socket made outside after the suite started: {path}",
            lambda path=path: connect(path))
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


def listening_unix_sockets_of_this_machine():
    """(path, socket type) of every listening Unix socket; an abstract one starts with @."""
    found = set()
    for row in pathlib.Path("/proc/net/unix").read_text().splitlines()[1:]:
        fields = row.split()
        if len(fields) >= 8 and int(fields[3], 16) & 0x10000:
            kind = socket.SOCK_SEQPACKET if fields[4] == "0005" else socket.SOCK_STREAM
            found.add((fields[7], int(kind)))
    return sorted(found)


@contextlib.contextmanager
def environment_set(values):
    saved = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def make_linked_worktree(scratch):
    """A repository and a worktree linked to it, whose .git is a file naming its git directory."""
    repository = scratch / "repository"
    repository.mkdir()
    git("init", "-q", cwd=repository)
    (repository / "tracked.txt").write_text("tracked\n")
    git("add", ".", cwd=repository)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "start",
        cwd=repository)
    checkout = scratch / "checkout"
    git("worktree", "add", "-q", "--detach", str(checkout), "HEAD", cwd=repository)
    return repository / ".git", checkout


def run_probe(scratch):
    """Run the probe as a suite in its test sandbox, and check every target after."""
    sandbox_prefix, unconfined_because = runner.signal_sandbox()
    if not sandbox_prefix:
        print(f"SKIP  every escape case: the runner builds no sandbox here: {unconfined_because}")
        return
    home = pathlib.Path(runner.REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX)
    runtime = pathlib.Path(runner.XDG_RUNTIME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX)
    name = f"run-all-test-suites-escape-test-{os.getpid()}"

    git_directory, checkout = make_linked_worktree(scratch)
    (checkout / PROBE_SUITE).write_text(X11_PROBE_SOURCE + PROBE_SOURCE)
    git_file_before = (checkout / ".git").read_text()
    # The run's log directory is placed in the home directory, as a run's often is; only
    # the suite's own input record in it is bound into the sandbox.
    log_dir = home / ".cache" / f"{name}-log"
    log_dir.mkdir(parents=True)
    recording_dir = log_dir / "recorded-inputs"
    recording_dir.mkdir()
    recorder_dir = runner.install_python_input_recorder(log_dir)
    strace = runner.strace_usable()
    hook_log, strace_dir = runner.recording_paths_for(recording_dir, PROBE_SUITE)
    sitecustomize = recorder_dir / "sitecustomize.py"
    sitecustomize_before = sitecustomize.read_text()

    canary_dir = home / ".cache" / name
    canary_dir.mkdir(parents=True)
    canary = canary_dir / "canary"
    canary.write_text("original")
    canary.chmod(0o644)
    symlink_target = canary_dir / "symlink-target"
    symlink_target.write_text("untouched")
    filter_marker = canary_dir / "filter-ran"
    host_tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"{name}-", dir="/tmp"))
    var_tmp_file = pathlib.Path("/var/tmp") / f"{name}-probe"
    dev_shm_file = pathlib.Path("/dev/shm") / f"{name}-probe"
    runtime_file = runtime / f"{name}-probe"
    outside_files = [host_tmp / "probe", var_tmp_file, dev_shm_file, runtime_file,
                     pathlib.Path("/etc") / f"{name}-probe"]
    runner_written = {
        "the suite's log": runner.log_path_for(log_dir, PROBE_SUITE),
        "another suite's log": runner.log_path_for(log_dir, "another-test.py"),
        "the report": log_dir / runner.REPORT_FILE_NAME,
        "the JUnit XML": log_dir / runner.JUNIT_XML_FILE_NAME,
        "the case times": log_dir / runner.TEST_CASE_TIMES_FILE_NAME,
        "the suite resource use": log_dir / runner.TEST_SUITE_RESOURCE_USE_FILE_NAME,
        "the machine readings": log_dir / runner.MACHINE_CPU_AND_MEMORY_READINGS_FILE_NAME,
        "the suite's input record": hook_log,
    }

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
    tcp_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_listener.bind(("127.0.0.1", 0))
    tcp_listener.listen(4)
    abstract_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    abstract_listener.bind("\0" + name)
    abstract_listener.listen(4)
    sleeper = subprocess.Popen(["sleep", "600"])
    system_v_key = 0x5e5c0000 + (os.getpid() & 0xffff)
    system_v_queue = subprocess.run(
        [sys.executable, "-c",
         "import ctypes, sys\n"
         "libc = ctypes.CDLL(None, use_errno=True)\n"
         f"print(libc.msgget({system_v_key}, 0o1600))\n"],
        capture_output=True, text=True).stdout.strip()
    git_before = git_directory_state(git_directory)
    credential_files = sorted(
        str(path) for pattern in CREDENTIAL_FILE_PATTERNS_THAT_MUST_BE_HIDDEN
        for path in home.glob(pattern) if path.is_file() and not path.name.endswith(".pub"))
    nonempty_credentials = [path for path in credential_files if os.path.getsize(path) > 0]
    # A credential under a name no list knows, in a directory of the home directory no
    # list names: hiding by default must hide it too.
    unlisted_directory = home / f".{name}-unlisted"
    unlisted_directory.mkdir()
    unlisted_credential = unlisted_directory / "oauth-token"
    unlisted_credential.write_text("planted-secret")
    credential_files.append(str(unlisted_credential))
    probe_file_name = f"{name}-probe"
    writable_directories = [*runner.directories_this_account_can_create_files_in_hidden_in_test_sandbox(),
                            str(home)]
    late_sockets = [pathlib.Path("/var/tmp") / f"{name}-late.sock", canary_dir / "late.sock"]
    late_ready, late_made = checkout / "late-sockets-ready", checkout / "late-sockets-made"
    late_listeners = []

    def make_late_sockets():
        deadline = time.monotonic() + 120
        while not late_ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        for path in late_sockets:
            late = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            late.bind(str(path))
            late.listen(1)
            late.setblocking(False)
            late_listeners.append(late)
        late_made.write_text("made")

    late_maker = threading.Thread(target=make_late_sockets, daemon=True)
    machine_sockets = [(path, kind) for path, kind in listening_unix_sockets_of_this_machine()
                       if path not in (str(runtime_socket_path), "@" + name)]

    targets = {
        "home_canary": str(canary),
        "home_new_file": str(canary_dir / "new-file"),
        "credential_files": credential_files,
        "outside_files": [str(path) for path in outside_files],
        "tmux_socket_name": name,
        "tmux_socket_path": str(tmux_socket_path),
        "runtime_socket_path": str(runtime_socket_path),
        "session_bus_path": str(runtime / "bus"),
        "machine_sockets": machine_sockets,
        "sleeper_pid": sleeper.pid,
        "system_v_key": system_v_key,
        "git_directory": str(git_directory),
        "checkout": str(checkout),
        "filter_marker": str(filter_marker),
        "outside_socket_variables": list(SOCKET_VARIABLES_THAT_MUST_BE_UNSET),
        "credential_variables": list(CREDENTIAL_VARIABLES_THAT_MUST_BE_UNSET),
        "recorder_sitecustomize": str(sitecustomize),
        "runner_written_paths": {label: str(path) for label, path in runner_written.items()},
        "symlink_target": str(symlink_target),
        "strace_directory": str(strace_dir) if strace else "",
        "checkout_file": str(checkout / "probe-stays"),
        "log_file": str(log_dir / "probe-was-here"),
        "hook_log": str(hook_log),
        "x11_displays": X11_DISPLAYS_PROBED,
        "writable_directories": writable_directories,
        "probe_file_name": probe_file_name,
        "late_sockets": [str(path) for path in late_sockets],
        "late_sockets_ready": str(late_ready),
        "late_sockets_made": str(late_made),
        "tcp_port": tcp_listener.getsockname()[1],
        "abstract_socket_name": name,
    }
    planted = {"ESCAPE_TEST_TARGETS": json.dumps(targets)}
    planted.update({variable: f"/outside/{variable.lower()}"
                    for variable in SOCKET_VARIABLES_THAT_MUST_BE_UNSET})
    planted.update({variable: f"secret-{variable.lower()}"
                    for variable in CREDENTIAL_VARIABLES_THAT_MUST_BE_UNSET})
    cgroup_unavailable = runner.why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none()
    # Descriptors held open, so the one the cgroup counters go to is numbered above 9, which
    # a shell such as dash cannot name.
    held_open = [open(os.devnull) for _ in range(12)]
    late_maker.start()
    try:
        with environment_set(planted):
            result = runner.run_one_suite(
                checkout, sys.executable, PROBE_SUITE, log_dir,
                recorder=(recorder_dir, recording_dir, strace), sandbox_prefix=sandbox_prefix,
                in_cgroup_scope=cgroup_unavailable is None, nice=True)
        # What the runner does with the suite's files after it ends, as a run does. A link
        # the suite could plant where the runner writes makes the runner refuse to write.
        try:
            runner.recording_of(checkout, PROBE_SUITE, result, recording_dir,
                                {PROBE_SUITE, "tracked.txt"}, "HEAD", strace is not None)
            runner.blob_hashes(checkout, ["tracked.txt"])
            runner.write_case_times_suite_resources_and_junit_xml_of_run(log_dir, [result])
            refused = None
        except OSError as error:
            refused = error
        check("after the suite, the runner reads its files and writes its records, finding no "
              "link the suite planted where it writes", refused is None, repr(refused))
        log_text = result["log"].read_text(errors="replace")
        attempts = {}
        for line in log_text.splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            attempts[record["attempt"]] = record
        check("the probe ran as a suite inside its test sandbox and reported",
              result["exit"] == 0 and len(attempts) > 40, (result["exit"], log_text[-1500:]))
        check("the probe ran in a cgroup scope of its own, as suites do, and its counters "
              "were read",
              cgroup_unavailable is not None or result["cpu_seconds"] is not None,
              (cgroup_unavailable, result.get("resources_note")))

        def blocked(attempt):
            record = attempts.get(attempt)
            return record is not None and not record["worked"], record

        outside_x11 = {}
        exec(X11_PROBE_SOURCE, outside_x11)
        displays_open_outside = []
        for display in X11_DISPLAYS_PROBED:
            try:
                if outside_x11["x11_display_accepts"](display):
                    displays_open_outside.append(display)
            except OSError:
                pass
        if displays_open_outside:
            check("precondition: outside, where the cookie can be read, the X11 probe opens "
                  f"display :{displays_open_outside[0]}", True)
        else:
            print("SKIP  precondition: no X11 display opens from outside either, so the X11 "
                  "cases show nothing on this machine")
        check("precondition: the tmux server of this test started",
              tmux_started.returncode == 0, tmux_started.stderr)
        check("precondition: at least one real credential file exists and is not empty",
              bool(nonempty_credentials), credential_files)
        check("precondition: the System V message queue of this test exists outside",
              system_v_queue.lstrip("-").isdigit() and int(system_v_queue) >= 0, system_v_queue)
        # A stopped daemon must not fail this test, so the named sockets are reported, not required.
        probed = {path for path, _ in machine_sockets}
        check("precondition: at least one listening socket outside /tmp and the runtime "
              "directory is among those probed",
              any(not path.startswith(("@", "/tmp/", "/run/user/")) for path in probed),
              sorted(probed))
        print("named machine sockets among those probed: "
              + (", ".join(path for path in MACHINE_SOCKETS_NAMED if path in probed) or "none"))

        # The home directory inside is empty but the suite's own, so it takes writes.
        for attempt in ("write the home canary", "create a file in the home directory"):
            record = attempts.get(attempt)
            check(f"inside, the home directory takes the write: {attempt}",
                  record is not None and record["worked"], record)
        for attempt in ("read the home canary", "chmod the home canary",
                        "rename the home canary", "delete the home canary"):
            ok, record = blocked(attempt)
            check(f"inside, the real home directory's file is not there: {attempt}", ok, record)
        check("outside afterwards, the home canary is unchanged: content, mode and name",
              canary.is_file() and canary.read_text() == "original"
              and (canary.stat().st_mode & 0o777) == 0o644
              and not (canary_dir / "canary.renamed").exists(),
              sorted(path.name for path in canary_dir.iterdir()))
        check("outside afterwards, a file created in the home directory is gone",
              not (canary_dir / "new-file").exists())
        for path in credential_files:
            ok, record = blocked(f"read credential file {path}")
            check(f"inside, a credential file is not there: {path}", ok, record)
        for directory in writable_directories:
            check(f"outside afterwards, nothing the suite wrote in {directory}, a directory "
                  f"this account can create files in, is there",
                  not (pathlib.Path(directory) / probe_file_name).exists())
        record = attempts.get("the late sockets were made outside")
        check("precondition: the sockets made outside after the suite started were made",
              record is not None and record["worked"], record)
        for path in late_sockets:
            ok, record = blocked(f"connect to a socket made outside after the suite started: {path}")
            check(f"inside, a socket made outside after the suite started cannot be reached: "
                  f"{path}", ok, record)
        for path in outside_files:
            check(f"outside afterwards, nothing was written at {path}", not path.exists())
        for attempt in ("reach the tmux server by name", "connect to the tmux server's socket",
                        "connect to the runtime directory's socket",
                        "connect to the session bus",
                        "start a process outside with systemd-run --user",
                        "write a ref in the repository's git directory",
                        "change the repository's git config", "create a branch with git",
                        "connect to a localhost TCP port outside",
                        "connect to an abstract Unix socket outside",
                        "reach a System V message queue outside",
                        "point the worktree's .git file at another git directory",
                        "change the input recorder's sitecustomize.py",
                        *(f"open an X11 connection to display :{display}"
                          for display in X11_DISPLAYS_PROBED)):
            ok, record = blocked(attempt)
            check(f"inside, this fails: {attempt}", ok, record)
        for path, _ in machine_sockets:
            ok, record = blocked(f"connect to the machine's listening socket {path}")
            check(f"inside, connecting to the machine's listening socket fails: {path}",
                  ok, record)
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
        check("outside afterwards, the worktree's .git file still names its git directory",
              (checkout / ".git").read_text() == git_file_before, (checkout / ".git").read_text())
        check("outside afterwards, no git filter planted in the checkout ran when the runner "
              "hashed the suite's files", not filter_marker.exists())
        check("outside afterwards, the input recorder's sitecustomize.py is unchanged",
              sitecustomize.read_text() == sitecustomize_before)
        check("outside afterwards, nothing the suite wrote in the run's log directory is "
              "there", not (log_dir / "probe-was-here").exists())
        check("outside afterwards, the file a planted link pointed at is unchanged",
              symlink_target.read_text() == "untouched")
        check("outside afterwards, the runner wrote its records as files of its own",
              all(not path.is_symlink() for path in runner_written.values()
                  if path.parent.exists()),
              [str(path) for path in runner_written.values() if path.is_symlink()])
        for variable in SOCKET_VARIABLES_THAT_MUST_BE_UNSET:
            ok, record = blocked(f"see variable {variable}")
            check(f"inside, the variable naming a socket outside is unset: {variable}", ok, record)
        for variable in CREDENTIAL_VARIABLES_THAT_MUST_BE_UNSET:
            ok, record = blocked(f"see variable {variable}")
            check(f"inside, the variable carrying a credential is unset: {variable}", ok, record)
        record = attempts.get("write in the checkout under test")
        check("inside, a write in the checkout under test works",
              record is not None and record["worked"], record)
        check("outside afterwards, a write in the checkout under test stays",
              (checkout / "probe-stays").is_file())
        record = attempts.get("write the suite's own input record")
        recorded = hook_log.read_text(errors="replace").splitlines()
        check("inside, the suite writes its own input record, which the runner reads after",
              record is not None and record["worked"]
              and "escape-test\tthe probe's own line" in recorded, record)
        check("inside, the input recorder, which the sandbox shows read-only, ran in the "
              "suite and recorded what it read",
              any(line.split("\t")[0] in ("read", "list", "probe", "git") for line in recorded),
              recorded[:5])

        # A suite allowed to write the git directory gets a copy-on-write overlay of it.
        (checkout / ".git").write_text(git_file_before)
        git_writer = next(iter(runner.SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY))
        environment = runner.launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed()
        written = subprocess.run(
            [*runner.command_prefix_starting_one_suite_in_its_test_sandbox(
                sandbox_prefix, checkout, suite=git_writer),
             "git", "-C", str(checkout), "branch", "escaped-by-git"],
            cwd=str(checkout), env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=120)
        check("inside, a suite given a copy of the git directory can create a branch",
              written.returncode == 0, written.stderr)
        check("outside afterwards, that branch is not in the repository's git directory",
              git_directory_state(git_directory) == git_before)
        # A checkout that is a repository's main worktree, in the home directory as
        # agent-seats' checkouts are: its .git directory sits inside the writable checkout,
        # and only the read-only bind of the git common directory keeps a suite out of it.
        main_worktree = home / ".cache" / f"{name}-main-worktree"
        main_worktree.mkdir(parents=True)
        try:
            git("init", "-q", cwd=main_worktree)
            (main_worktree / "tracked.txt").write_text("tracked\n")
            git("add", ".", cwd=main_worktree)
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "start",
                cwd=main_worktree)
            main_git_before = git_directory_state(main_worktree / ".git")
            tried = subprocess.run(
                [*runner.command_prefix_starting_one_suite_in_its_test_sandbox(
                    sandbox_prefix, main_worktree, suite=PROBE_SUITE),
                 "sh", "-c",
                 "echo 0000000000000000000000000000000000000000 > .git/refs/heads/escaped; "
                 "echo '[escaped]' >> .git/config; git branch escaped-by-git; "
                 "test ! -e .git/refs/heads/escaped && test ! -e .git/refs/heads/escaped-by-git"],
                cwd=str(main_worktree), env=environment, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=120)
            check("inside, a suite cannot write the git directory of a checkout that is a "
                  "main worktree: no ref, no config, no branch",
                  tried.returncode == 0, (tried.returncode, tried.stderr[-600:]))
            check("outside afterwards, that main worktree's git directory is unchanged",
                  git_directory_state(main_worktree / ".git") == main_git_before)
        finally:
            shutil.rmtree(main_worktree, ignore_errors=True)
        # A suite listed to share the machine's network reaches the same port.
        shared = "scripts/shares-the-machine-network-for-this-case-test.py"
        runner.SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK[shared] = "this case"
        try:
            reached = subprocess.run(
                [*runner.command_prefix_starting_one_suite_in_its_test_sandbox(
                    sandbox_prefix, checkout, suite=shared),
                 sys.executable, "-c",
                 "import socket, sys\n"
                 f"socket.create_connection(('127.0.0.1', {targets['tcp_port']}), timeout=3).close()\n"],
                cwd=str(checkout), env=environment, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=120)
        finally:
            del runner.SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK[shared]
        check("inside, a suite listed to share the machine's network reaches a localhost port "
              "outside", reached.returncode == 0, reached.stderr)
    finally:
        for handle in held_open:
            handle.close()
        late_maker.join(5)
        for late in late_listeners:
            late.close()
        for path in late_sockets:
            path.unlink(missing_ok=True)
        shutil.rmtree(unlisted_directory, ignore_errors=True)
        for directory in writable_directories:
            try:
                (pathlib.Path(directory) / probe_file_name).unlink(missing_ok=True)
            except OSError:
                pass
        sleeper.kill()
        sleeper.wait()
        listener.close()
        tcp_listener.close()
        abstract_listener.close()
        runtime_socket_path.unlink(missing_ok=True)
        subprocess.run([sys.executable, "-c",
                        "import ctypes\n"
                        "libc = ctypes.CDLL(None)\n"
                        f"queue = libc.msgget({system_v_key}, 0)\n"
                        "queue >= 0 and libc.msgctl(queue, 0, None)\n"], capture_output=True)
        subprocess.run(["tmux", "-L", name, "kill-server"], env=tmux_environment,
                       capture_output=True)
        shutil.rmtree(canary_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)
        shutil.rmtree(host_tmp, ignore_errors=True)
        for path in outside_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def check_runner_writes_and_reads_refuse_symbolic_links(scratch):
    """The runner's own file access refuses a link a suite could have left in its place."""
    target = scratch / "link-target"
    target.write_text("untouched")
    link = scratch / "planted-link"
    link.symlink_to(target)
    try:
        with runner.open_for_writing_without_following_symlinks(link) as handle:
            handle.write("written through the link")
        refused = False
    except OSError:
        refused = True
    check("the runner refuses to write a record through a symbolic link",
          refused and target.read_text() == "untouched", target.read_text())
    try:
        runner.read_text_without_following_symlinks(link)
        refused = False
    except OSError:
        refused = True
    check("the runner refuses to read a suite's file through a symbolic link", refused)
    pipe = scratch / "planted-pipe"
    os.mkfifo(pipe)
    try:
        runner.read_text_without_following_symlinks(pipe)
        refused = False
    except OSError:
        refused = True
    check("the runner refuses to read a named pipe left among a suite's files, rather than "
          "wait on it", refused)


def check_blob_hashes_run_no_filter(scratch):
    """Hashing a checkout's files runs no filter the checkout's git configuration names."""
    repository = scratch / "filtered"
    repository.mkdir()
    git("init", "-q", cwd=repository)
    marker = scratch / "filter-ran"
    git("config", "filter.planted.clean", f"touch {marker}; cat", cwd=repository)
    (repository / ".gitattributes").write_text("* filter=planted\n")
    (repository / "file.txt").write_text("content\n")
    hashes = runner.blob_hashes(repository, ["file.txt"])
    check("hashing a file whose attributes name a filter runs no filter",
          not marker.exists() and hashes.get("file.txt") not in (None, "unknown"), hashes)


with tempfile.TemporaryDirectory() as scratch_name:
    check_runner_writes_and_reads_refuse_symbolic_links(pathlib.Path(scratch_name))
with tempfile.TemporaryDirectory() as scratch_name:
    check_blob_hashes_run_no_filter(pathlib.Path(scratch_name))

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
