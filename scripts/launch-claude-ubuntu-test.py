#!/usr/bin/env python3
"""Tests for launch-claude-ubuntu's remote command composition.

The launcher's values cross two shell parses: the box's login shell parses
the whole ssh command (P1), and tmux's shell parses the pane command it was
handed (P2). Getting a value through both intact is the launcher's hardest
job, and hand-derived quoting there has failed before (PR #134's review
arc), so these cases MEASURE the journey instead of deriving it:

  launcher (real, on this Mac; ssh stubbed, remote string captured)
    -> P1: the captured remote string run by a real /bin/sh, with tmux,
       python3, git and timeout stubbed and HOME sandboxed
    -> P2: the tmux stub extracts its pane-command argument and runs it
       through a real sh; the python3 stub captures the final supervisor
       argv — the exact words the box-side supervisor would receive.

The layer model itself is pinned by the default-root pair: tmux's -c value
must arrive tilde-EXPANDED (the box shell resolves it at P1), while the
supervisor's --cd arrives as the literal ~ path (handoff-supervisor.py
expanduser()s it live, handoff-supervisor.py:855).

Run: python3 scripts/launch-claude-ubuntu-test.py

The suite is self-contained (this file plus launch-claude-ubuntu and
agent-binary-update-under-lock.py beside it; every other participant is
stubbed, and the helper is copied into the sandbox HOME's checkout path,
where the box-side command looks for it) and runs unmodified ON THE BOX,
where P1 is parsed by the real /bin/sh (dash) instead of macOS sh standing
in — the one caveat the PR #137/#139 reviews carried (user-directed
2026-08-22):
  scp scripts/launch-claude-ubuntu scripts/launch-claude-ubuntu-test.py scripts/agent-binary-update-under-lock.py ned:/tmp/x/
  ssh ned 'cd /tmp/x && chmod +x launch-claude-ubuntu && python3 launch-claude-ubuntu-test.py'
"""

import fcntl
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

LAUNCHER = Path(__file__).with_name("launch-claude-ubuntu")
UPDATE_LOCK_HELPER_NAME = "agent-binary-update-under-lock.py"
UPDATE_LOCK_HELPER = Path(__file__).with_name(UPDATE_LOCK_HELPER_NAME)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def write_stub(directory: Path, name: str, body: str):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


class LaunchHarness:
    """One sandbox: stubs, a throwaway HOME, and the three-layer replay."""

    def __init__(self, root: Path):
        self.captures = root / "captures"
        self.captures.mkdir(parents=True)
        self.home = root / "home"
        self.home.mkdir()
        # Both the launcher and the P1 replay run from here, so any
        # relative-path side effect lands in the sandbox — the #139 review
        # measured the replay writing a literal ~alice directory into the
        # suite-runner's own cwd against the pre-fix launcher.
        self.workdir = root / "workdir"
        self.workdir.mkdir()
        self.stubs = root / "stubs"
        self.stubs.mkdir()
        # The box-side update runs the update-lock helper from the box's
        # checkout, $HOME/Projects/nedschorus/scripts, so the helper under
        # test is copied to that path in the sandbox HOME.
        checkout_scripts = self.home / "Projects" / "nedschorus" / "scripts"
        checkout_scripts.mkdir(parents=True)
        shutil.copy(UPDATE_LOCK_HELPER, checkout_scripts / UPDATE_LOCK_HELPER_NAME)
        write_stub(self.stubs, "ssh",
                   'printf \'%s\\n\' "$@" > "$LCU_TEST_DIR/ssh-argv.txt"\n'
                   'exit 0\n')
        write_stub(self.stubs, "timeout", "exit 0\n")
        # The helper really runs `claude update`, so claude is stubbed: each
        # update records whether the release marker of a lock held by the
        # test (LCU_RELEASE_MARKER) existed yet when it ran.
        write_stub(self.stubs, "claude",
                   '[ "${1:-}" = "update" ] || exit 0\n'
                   'if [ -e "${LCU_RELEASE_MARKER:-/nonexistent}" ]; '
                   'then echo after-release; else echo before-release; fi '
                   '>> "$LCU_TEST_DIR/claude-updates.txt"\n')
        write_stub(self.stubs, "git", "exit 0\n")
        # The remote side asks whether the box's own seat restart is still
        # running; "inactive" is the answer on a box that has been up a while,
        # so no case waits unless it says so. sleep records instead of
        # sleeping, on both sides of the transport.
        write_stub(self.stubs, "systemctl", 'echo "${LCU_UNIT_STATE:-inactive}"\n')
        write_stub(self.stubs, "sleep",
                   'printf \'%s\\n\' "$1" >> "$LCU_TEST_DIR/sleep-calls.txt"\n')
        # The supervisor call also records its ENVIRONMENT, not just its argv:
        # the task-list binding is an exported variable, so the only place it
        # can be measured is the environment of the process the pane command
        # actually starts.
        # The update-lock helper is the one call handed to the REAL
        # interpreter, keyed on its own name, so every other python3 the
        # box-side command runs stays stubbed.
        write_stub(self.stubs, "python3",
                   '{ printf \'%s\\n\' "$@"; echo "=== call boundary ==="; } '
                   '>> "$LCU_TEST_DIR/python3-calls.txt"\n'
                   f'case "${{1:-}}" in (*{UPDATE_LOCK_HELPER_NAME}) '
                   f'exec "{sys.executable}" "$@";; esac\n'
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (*handoff-supervisor.py*)\n'
                   '    { echo "CLAUDE_CODE_TASK_LIST_ID='
                   '${CLAUDE_CODE_TASK_LIST_ID-<unset>}";\n'
                   '      echo "CLAUDE_CODE_ENABLE_TODO_TOOLS='
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}"; } '
                   '> "$LCU_TEST_DIR/supervisor-environment.txt";;\n'
                   '  esac\n'
                   'done\n'
                   'exit 0\n')
        # The attached pane ends in `exec $SHELL`; this stand-in records the
        # directory that shell would start in — the after-exit cd's actual
        # landing point, which exit codes alone cannot pin (a failed cd is
        # followed by an exec that succeeds anyway) — and its environment,
        # which is where the `claude --continue` that shell offers would read
        # its task-list binding from.
        write_stub(self.stubs, "record-shell",
                   'pwd > "$LCU_TEST_DIR/after-exit-cwd.txt"\n'
                   '{ echo "CLAUDE_CODE_TASK_LIST_ID='
                   '${CLAUDE_CODE_TASK_LIST_ID-<unset>}";\n'
                   '  echo "CLAUDE_CODE_ENABLE_TODO_TOOLS='
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}"; } '
                   '> "$LCU_TEST_DIR/after-exit-environment.txt"\n')
        # has-session answers "no session" so socket selection stays on the
        # per-seat socket; a new-session call records its argv, then replays
        # its pane-command argument through a real sh — parse 2.
        write_stub(self.stubs, "tmux",
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (has-session) exit 1;; esac\n'
                   'done\n'
                   'printf \'%s\\n\' "$@" > "$LCU_TEST_DIR/tmux-argv.txt"\n'
                   'previous=""; pane_command=""; pane_directory=""\n'
                   'for argument in "$@"; do\n'
                   '  [ "$previous" = "-c" ] && pane_directory=$argument\n'
                   '  case "$argument" in (*handoff-supervisor.py*) '
                   'pane_command=$argument;; esac\n'
                   '  previous=$argument\n'
                   'done\n'
                   'printf \'%s\' "$pane_directory" '
                   '> "$LCU_TEST_DIR/tmux-pane-directory.txt"\n'
                   'if [ -n "$pane_command" ]; then sh -c "$pane_command"; fi\n'
                   'exit 0\n')

    def replay_environment(self):
        environment = {
            "PATH": f"{self.stubs}:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(self.home),
            "SHELL": str(self.stubs / "record-shell"),
            "LCU_TEST_DIR": str(self.captures),
            "LCU_UNIT_STATE": self.unit_state,
            "LCU_RELEASE_MARKER": str(self.release_marker),
        }
        # Box-side, as on the real box: the update limit is read from the
        # box shell's environment, not carried from this Mac.
        if self.update_timeout_seconds is not None:
            environment["LAUNCH_CLAUDE_UPDATE_TIMEOUT_SECONDS"] = str(
                self.update_timeout_seconds)
        return environment

    unit_state = "inactive"
    update_timeout_seconds = None

    @property
    def release_marker(self):
        return self.captures.parent / "update-lock-released"

    def update_lock_path(self):
        return self.home / ".local" / "state" / "claude" / "agent-binary-update.lock"

    def claude_updates(self):
        path = self.captures / "claude-updates.txt"
        return (path.read_text(encoding="utf-8").splitlines()
                if path.is_file() else [])

    def seat_exists_on_the_box(self, after_polls: int = 0):
        """Make the tmux stub answer has-session with "exists" — at once, or
        only after after_polls polls have failed, the way a seat the box is
        restarting appears part-way through the wait. One poll is two
        has-session calls: the per-seat socket, then the default one."""
        after_polls *= 2
        tmux = self.stubs / "tmux"
        tmux.write_text(tmux.read_text(encoding="utf-8").replace(
            '  case "$argument" in (has-session) exit 1;; esac\n',
            '  case "$argument" in (has-session) '
            'echo x >> "$LCU_TEST_DIR/has-session-calls.txt"; '
            f'[ "$(wc -l < "$LCU_TEST_DIR/has-session-calls.txt")" -gt {after_polls} ] '
            '&& exit 0 || exit 1;; esac\n'), encoding="utf-8")

    def ssh_answers(self, exit_codes):
        """Make the ssh stub exit with each code in turn, the last one
        repeating: [255, 255, 0] is a box that answers on the third try."""
        codes = " ".join(str(code) for code in exit_codes)
        write_stub(self.stubs, "ssh",
                   'printf \'%s\\n\' "$@" > "$LCU_TEST_DIR/ssh-argv.txt"\n'
                   'echo x >> "$LCU_TEST_DIR/ssh-calls.txt"\n'
                   'n=$(wc -l < "$LCU_TEST_DIR/ssh-calls.txt")\n'
                   f'set -- {codes}\n'
                   'while [ $# -gt 1 ] && [ "$n" -gt 1 ]; do shift; n=$((n - 1)); done\n'
                   'exit "$1"\n')

    def clock_advances(self, seconds_per_call: int):
        """Make `date +%s` answer a clock that moves seconds_per_call per
        call: the launcher reads it before and after each ssh, so this is
        how long each attach appears to have lasted."""
        write_stub(self.stubs, "date",
                   'echo x >> "$LCU_TEST_DIR/date-calls.txt"\n'
                   f'echo $(( $(wc -l < "$LCU_TEST_DIR/date-calls.txt") * {seconds_per_call} ))\n')

    def count(self, capture_name: str) -> int:
        path = self.captures / capture_name
        return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0

    def prepare_ran(self) -> bool:
        """The prepare step's trust mark is a python3 -c call naming
        hasTrustDialogAccepted; the supervisor call never does."""
        calls = self.captures / "python3-calls.txt"
        return calls.is_file() and "hasTrustDialogAccepted" in calls.read_text(encoding="utf-8")

    def run(self, launcher_arguments, agents_root=None, extra_arguments=None):
        """Launcher -> captured remote string -> P1 replay (-> P2 inside the
        tmux stub). Returns a dict of everything observable."""
        for leftover in self.captures.iterdir():
            leftover.unlink()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("NEDSCHORUS_", "LAUNCH_CLAUDE_"))}
        environment["PATH"] = f"{self.stubs}:{environment.get('PATH', '')}"
        environment["LCU_TEST_DIR"] = str(self.captures)
        environment["NEDSCHORUS_AGENT_BOX"] = "stub-box"
        if agents_root is not None:
            environment["NEDSCHORUS_AGENTS_ROOT"] = agents_root
        if extra_arguments is not None:
            environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = extra_arguments
        launched = subprocess.run(
            [str(LAUNCHER), *launcher_arguments],
            capture_output=True, text=True, check=False, env=environment,
            cwd=str(self.workdir))
        ssh_capture = self.captures / "ssh-argv.txt"
        remote = (ssh_capture.read_text(encoding="utf-8").splitlines()[-1]
                  if ssh_capture.is_file() else "")
        replayed = subprocess.run(
            ["/bin/sh", "-c", remote], capture_output=True, text=True,
            check=False, env=self.replay_environment(), cwd=str(self.workdir))
        pane_directory_capture = self.captures / "tmux-pane-directory.txt"
        supervisor_environment_capture = (self.captures
                                          / "supervisor-environment.txt")
        after_exit_environment_capture = (self.captures
                                          / "after-exit-environment.txt")
        calls_capture = self.captures / "python3-calls.txt"
        supervisor_argv = []
        if calls_capture.is_file():
            for block in calls_capture.read_text(encoding="utf-8").split(
                    "=== call boundary ===\n"):
                lines = [line for line in block.splitlines() if line]
                if any("handoff-supervisor.py" in line for line in lines):
                    supervisor_argv = lines
        return {
            "launched": launched,
            "remote": remote,
            "replay": replayed,
            "pane_directory": (pane_directory_capture.read_text(encoding="utf-8")
                               if pane_directory_capture.is_file() else ""),
            "supervisor_argv": supervisor_argv,
            "supervisor_environment": environment_lines(
                supervisor_environment_capture),
            "after_exit_environment": environment_lines(
                after_exit_environment_capture),
        }


def environment_lines(capture: Path) -> dict:
    """A `NAME=value` capture file as a dict; {} when nothing was recorded."""
    if not capture.is_file():
        return {}
    recorded = {}
    for line in capture.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            name, _, value = line.partition("=")
            recorded[name] = value
    return recorded


def argv_value(argv, flag):
    """The argv token following the flag, or None."""
    for index, token in enumerate(argv):
        if token == flag and index + 1 < len(argv):
            return argv[index + 1]
    return None


class AnotherUpdateHoldsTheLock:
    """Hold the machine's update lock from this test, as another update would,
    releasing it after release_after_seconds (None: held until the block ends).
    The release marker is written BEFORE the lock is released, so an update
    that ran only after taking the lock always sees it."""

    def __init__(self, lock_path: Path, release_marker: Path,
                 release_after_seconds=None):
        self.lock_path = lock_path
        self.release_marker = release_marker
        self.release_after_seconds = release_after_seconds
        self.timer = None

    def release(self):
        self.release_marker.write_text("released", encoding="utf-8")
        fcntl.flock(self.lock_file, fcntl.LOCK_UN)

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file = open(self.lock_path, "a")
        fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if self.release_after_seconds is not None:
            self.timer = threading.Timer(self.release_after_seconds, self.release)
            self.timer.start()
        return self

    def __exit__(self, *exception):
        if self.timer is not None:
            self.timer.join()
        self.lock_file.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="launch-claude-ubuntu-test-") as scratch:
        root = Path(scratch)

        # --- 1. default root, detached: the layer-model pair ---------------
        harness = LaunchHarness(root / "default-root")
        result = harness.run(["seat-a", "--no-attach"])
        check("default root: the remote string parses and runs (P1 exit 0)",
              result["replay"].returncode == 0,
              (result["replay"].returncode, result["replay"].stderr))
        check("default root: tmux -c arrives tilde-EXPANDED (P1 resolved it)",
              result["pane_directory"] == f"{harness.home}/agents/seat-a",
              result["pane_directory"])
        check("default root: supervisor --cd arrives as the LITERAL ~ path",
              argv_value(result["supervisor_argv"], "--cd") == "~/agents/seat-a",
              result["supervisor_argv"])
        check("default root: the supervisor script rides the box's own $HOME",
              result["supervisor_argv"]
              and result["supervisor_argv"][0]
              == (f"{harness.home}/Projects/nedschorus"
                  "/nc-systems/handoff/handoff-supervisor.py"),
              result["supervisor_argv"])
        check("default root: the seat directory was created at P1",
              (harness.home / "agents" / "seat-a").is_dir(),
              str(harness.home / "agents"))

        # --- 1b. the launcher itself must have reached ssh — without this,
        # a launcher that exits before the transport leaves an empty remote
        # string, and sh -c "" exits 0, passing the parse checks vacuously
        # (PR #137 review P3).
        check("default root: the launcher reached ssh and exited 0",
              result["launched"].returncode == 0 and result["remote"],
              (result["launched"].returncode, result["launched"].stderr[:200]))

        # --- 1c. a ~user root is REFUSED before any transport (user-ruled
        # 2026-08-22: overrides either work or are blocked) — the box shell
        # and the fleet's Python tools would resolve it to different
        # directories, silently splitting the seat.
        harness = LaunchHarness(root / "tilde-user")
        result = harness.run(["seat-u", "--no-attach"],
                             agents_root="~alice/agents")
        check("tilde-user root: refused with exit 2, naming the split",
              result["launched"].returncode == 2
              and "not supported" in result["launched"].stderr
              and "splitting the seat" in result["launched"].stderr,
              (result["launched"].returncode, result["launched"].stderr[:200]))
        check("tilde-user root: nothing was sent to the box",
              result["remote"] == "", result["remote"][:200])

        # --- 1d. a ~/ root with a space rides the supported tilde carry ----
        harness = LaunchHarness(root / "tilde-space")
        result = harness.run(["seat-h", "--no-attach"],
                             agents_root="~/custom agents")
        check("~/ root with a space: tmux -c resolves under the box home",
              result["replay"].returncode == 0
              and result["pane_directory"]
              == f"{harness.home}/custom agents/seat-h",
              (result["replay"].returncode, result["pane_directory"]))
        check("~/ root with a space: supervisor --cd stays the literal ~ path",
              argv_value(result["supervisor_argv"], "--cd")
              == "~/custom agents/seat-h",
              result["supervisor_argv"])

        # --- 2. apostrophe + space in the agents root ----------------------
        harness = LaunchHarness(root / "apostrophe-root")
        apostrophe_root = f"{harness.home}/agent's fleet"
        result = harness.run(["seat-b", "--no-attach"], agents_root=apostrophe_root)
        check("apostrophe root: the remote string still parses and runs",
              result["replay"].returncode == 0,
              (result["replay"].returncode, result["replay"].stderr[:300]))
        check("apostrophe root: tmux -c carries the path byte-intact",
              result["pane_directory"] == f"{apostrophe_root}/seat-b",
              result["pane_directory"])
        check("apostrophe root: supervisor --cd carries the path byte-intact",
              argv_value(result["supervisor_argv"], "--cd")
              == f"{apostrophe_root}/seat-b",
              result["supervisor_argv"])
        check("apostrophe root: the seat directory was created where assessed",
              Path(f"{apostrophe_root}/seat-b").is_dir(), apostrophe_root)

        # --- 3. $ in the agents root is literal, not expanded --------------
        harness = LaunchHarness(root / "dollar-root")
        dollar_root = f"{harness.home}/pre$HOME-root"
        result = harness.run(["seat-c", "--no-attach"], agents_root=dollar_root)
        check("dollar root: $ in the path survives both parses unexpanded",
              result["replay"].returncode == 0
              and argv_value(result["supervisor_argv"], "--cd")
              == f"{dollar_root}/seat-c"
              and result["pane_directory"] == f"{dollar_root}/seat-c",
              (result["pane_directory"],
               argv_value(result["supervisor_argv"], "--cd")))

        # --- 4. --first-prompt-file with apostrophe and $ -------------------
        harness = LaunchHarness(root / "prompt-file")
        prompt_path = f"{harness.home}/agent's $prompts/boot.md"
        result = harness.run(
            ["seat-d", "--no-attach", "--first-prompt-file", prompt_path])
        check("first-prompt-file: apostrophe and $ reach the supervisor intact",
              result["replay"].returncode == 0
              and argv_value(result["supervisor_argv"], "--first-prompt-file")
              == prompt_path,
              (result["replay"].returncode,
               argv_value(result["supervisor_argv"], "--first-prompt-file"),
               result["replay"].stderr[:200]))

        # --- 5. the extra-arguments hook: caller quotes for the supervisor's
        # shell parse (shlex.quote, as resupervise-seat.py composes it); the
        # launcher owns its transport's transparency ------------------------
        harness = LaunchHarness(root / "hook")
        hook_path = f"{harness.home}/agent's $handoffs"
        result = harness.run(
            ["seat-e", "--no-attach"],
            extra_arguments=f"--handoff-dir {shlex.quote(hook_path)}")
        check("hook: a shlex-quoted apostrophe-and-$ value arrives byte-intact",
              result["replay"].returncode == 0
              and argv_value(result["supervisor_argv"], "--handoff-dir")
              == hook_path,
              (result["replay"].returncode,
               argv_value(result["supervisor_argv"], "--handoff-dir")))

        # --- 6. attached launch: the trap/after-exit wrapper executes ------
        harness = LaunchHarness(root / "attached")
        result = harness.run(["seat-f"])
        tmux_argv_path = harness.captures / "tmux-argv.txt"
        tmux_argv = (tmux_argv_path.read_text(encoding="utf-8").splitlines()
                     if tmux_argv_path.is_file() else [])
        check("attached: new-session -A with the wrapper executes to exit 0",
              result["replay"].returncode == 0 and "-A" in tmux_argv
              and argv_value(result["supervisor_argv"], "--cd")
              == "~/agents/seat-f",
              (result["replay"].returncode, result["replay"].stderr[:200]))
        after_exit_cwd = harness.captures / "after-exit-cwd.txt"
        check("attached: the after-exit shell starts in the seat directory",
              after_exit_cwd.is_file()
              # resolve() both sides: macOS reports /var for /private/var
              and Path(after_exit_cwd.read_text(encoding="utf-8").strip()).resolve()
              == (harness.home / "agents" / "seat-f").resolve(),
              (after_exit_cwd.read_text(encoding="utf-8").strip()
               if after_exit_cwd.is_file() else "no shell recorded"))

        # --- 7. attached launch under an apostrophe root: the after-exit
        # shell's cd target is the seat directory ---------------------------
        harness = LaunchHarness(root / "attached-apostrophe")
        apostrophe_root = f"{harness.home}/agent's fleet"
        result = harness.run(["seat-g"], agents_root=apostrophe_root)
        check("attached + apostrophe root: wrapper executes and paths hold",
              result["replay"].returncode == 0
              and result["pane_directory"] == f"{apostrophe_root}/seat-g"
              and argv_value(result["supervisor_argv"], "--cd")
              == f"{apostrophe_root}/seat-g",
              (result["replay"].returncode, result["replay"].stderr[:300]))
        after_exit_cwd = harness.captures / "after-exit-cwd.txt"
        check("attached + apostrophe root: the after-exit shell lands in the seat",
              after_exit_cwd.is_file()
              and Path(after_exit_cwd.read_text(encoding="utf-8").strip()).resolve()
              == Path(f"{apostrophe_root}/seat-g").resolve(),
              (after_exit_cwd.read_text(encoding="utf-8").strip()
               if after_exit_cwd.is_file() else "no shell recorded"))

        # --- 8. task-list persistence: both variables reach the box-side
        # supervisor's environment, and the list id is derived from the SEAT
        # NAME. Two different seat names in one suite are the teeth here: an
        # id leaking in from the ambient environment rather than being
        # composed per seat would give both runs the same value. (The P1
        # replay environment is a whitelist — PATH, HOME, SHELL, LCU_TEST_DIR
        # — so a leak would have to come through the composed string itself.)
        harness = LaunchHarness(root / "task-list-detached")
        result = harness.run(["seat-h", "--no-attach"])
        check("task list: the pin reaches the supervisor as nedschorus-<seat>-tasks",
              result["supervisor_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-h-tasks",
              result["supervisor_environment"])
        check("task list: the task tools are enabled for the supervisor",
              result["supervisor_environment"].get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              result["supervisor_environment"])
        # --- task-list migration, box-side (user-ruled 2026-08-29): the
        # rename rides inside the pane command, so it runs under the box's
        # own $HOME; an existing prefixed store is never overwritten. -------
        harness = LaunchHarness(root / "task-list-migration")
        unprefixed_store = harness.home / ".claude" / "tasks" / "seat-h-tasks"
        unprefixed_store.mkdir(parents=True)
        (unprefixed_store / "1.json").write_text('{"id": "1"}',
                                                 encoding="utf-8")
        result = harness.run(["seat-h", "--no-attach"])
        prefixed_store = (harness.home / ".claude" / "tasks"
                          / "nedschorus-seat-h-tasks")
        check("migration: the unprefixed store is renamed to the prefixed id",
              not unprefixed_store.exists()
              and (prefixed_store / "1.json").is_file(),
              sorted(str(p) for p in
                     (harness.home / ".claude" / "tasks").glob("*")))
        harness = LaunchHarness(root / "task-list-migration-no-clobber")
        unprefixed_store = harness.home / ".claude" / "tasks" / "seat-h-tasks"
        unprefixed_store.mkdir(parents=True)
        (unprefixed_store / "1.json").write_text("unprefixed",
                                                 encoding="utf-8")
        prefixed_store = (harness.home / ".claude" / "tasks"
                          / "nedschorus-seat-h-tasks")
        prefixed_store.mkdir(parents=True)
        (prefixed_store / "2.json").write_text("prefixed", encoding="utf-8")
        result = harness.run(["seat-h", "--no-attach"])
        check("migration: an existing prefixed store is never overwritten",
              unprefixed_store.is_dir()
              and (prefixed_store / "2.json").is_file()
              and not (prefixed_store / "1.json").exists(),
              sorted(str(p) for p in
                     (harness.home / ".claude" / "tasks").glob("*")))

        harness = LaunchHarness(root / "task-list-second-seat")
        result = harness.run(["seat-i", "--no-attach"])
        check("task list: a second seat name yields a DIFFERENT list id",
              result["supervisor_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-i-tasks",
              result["supervisor_environment"])

        # --- 9. the same binding on the ATTACHED path, including the
        # after-exit shell: that shell offers `claude --continue`, and a
        # continue run without the pin binds to a session-keyed store whose
        # TaskList returns empty with no error.
        harness = LaunchHarness(root / "task-list-attached")
        result = harness.run(["seat-j"])
        check("task list (attached): the supervisor gets nedschorus-<seat>-tasks",
              result["supervisor_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-j-tasks"
              and result["supervisor_environment"].get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              result["supervisor_environment"])
        check("task list (attached): the after-exit shell keeps the binding",
              result["after_exit_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-j-tasks"
              and result["after_exit_environment"].get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              result["after_exit_environment"])

        # --- the window role (nedschorus#116, user-ruled 2026-09-14): an
        # attached window reconnects on its own, and the remote side neither
        # re-prepares a live seat nor races the box's own restart.

        # 9. An attach onto a seat that already exists skips the prepare
        # step: nothing to prepare, and N windows reconnecting after a boot
        # would otherwise each run `claude update` under live sessions.
        harness = LaunchHarness(root / "attach-existing-seat")
        harness.seat_exists_on_the_box()
        result = harness.run(["seat-k"])
        check("attach onto a live seat: the prepare step does not run",
              result["replay"].returncode == 0 and not harness.prepare_ran(),
              (result["replay"].returncode, result["replay"].stderr[:200]))
        check("attach onto a live seat: the attach itself still happens",
              "handoff-supervisor.py" in " ".join(result["supervisor_argv"]),
              result["supervisor_argv"])
        harness = LaunchHarness(root / "attach-new-seat")
        result = harness.run(["seat-l"])
        check("attach onto no seat: the prepare step runs, and nothing waited",
              result["replay"].returncode == 0 and harness.prepare_ran()
              and harness.count("sleep-calls.txt") == 0,
              (result["replay"].returncode, harness.count("sleep-calls.txt")))

        # 10. The box is restarting its seats after a boot (the unit is
        # activating) and the seat is not back yet: the remote side polls
        # until the seat appears, then attaches without preparing.
        harness = LaunchHarness(root / "wait-for-the-box-restart")
        harness.unit_state = "activating"
        harness.seat_exists_on_the_box(after_polls=2)
        result = harness.run(["seat-m"])
        check("box restarting: the remote side waits, says so, and attaches once the seat is back",
              result["replay"].returncode == 0
              and harness.count("sleep-calls.txt") == 2
              and "waiting for seat-m before attaching" in result["replay"].stdout
              and not harness.prepare_ran(),
              (result["replay"].returncode, harness.count("sleep-calls.txt"),
               result["replay"].stdout[:200], harness.prepare_ran()))
        harness = LaunchHarness(root / "wait-bounded")
        harness.unit_state = "activating"
        result = harness.run(["seat-n"])
        check("box restarting but the seat never returns: the wait is bounded at 180s, "
              "then the seat is prepared and created",
              result["replay"].returncode == 0
              and harness.count("sleep-calls.txt") == 90 and harness.prepare_ran(),
              (result["replay"].returncode, harness.count("sleep-calls.txt")))

        # 11. The connection drops (ssh exit 255): the launcher waits, doubling
        # to 30s, and tries again; any other exit ends it as before, and a
        # detached launch never retries.
        harness = LaunchHarness(root / "reconnect")
        harness.ssh_answers([255, 255, 0])
        result = harness.run(["seat-o"])
        check("a dropped connection is retried until the box answers, then the launcher exits 0",
              result["launched"].returncode == 0 and harness.count("ssh-calls.txt") == 3,
              (result["launched"].returncode, harness.count("ssh-calls.txt"),
               result["launched"].stderr[:300]))
        check("each retry says so, names the seat, and doubles the wait",
              result["launched"].stderr.count("retrying in") == 2
              and "seat-o" in result["launched"].stderr
              and "Ctrl-C" in result["launched"].stderr
              and (harness.captures / "sleep-calls.txt").read_text(encoding="utf-8").split()
              == ["2", "4"],
              result["launched"].stderr[:400])
        # The wait resets after a session that actually ran: with each ssh
        # appearing to last 100s, every drop is a live attach lost, and each
        # retry starts from 2s; with each lasting 1s, they are failed
        # attempts and the wait keeps doubling (PR #365 review).
        harness = LaunchHarness(root / "reconnect-after-long-sessions")
        harness.ssh_answers([255, 255, 255, 0])
        harness.clock_advances(100)
        result = harness.run(["seat-o2"])
        check("a drop after a long session retries from 2s again, not from the doubled wait",
              result["launched"].returncode == 0
              and (harness.captures / "sleep-calls.txt").read_text(encoding="utf-8").split()
              == ["2", "2", "2"],
              (result["launched"].returncode,
               (harness.captures / "sleep-calls.txt").read_text(encoding="utf-8")
               if (harness.captures / "sleep-calls.txt").is_file() else None))
        harness = LaunchHarness(root / "reconnect-after-short-attempts")
        harness.ssh_answers([255, 255, 255, 0])
        harness.clock_advances(1)
        result = harness.run(["seat-o3"])
        check("drops after short attempts keep doubling: 2, 4, 8",
              result["launched"].returncode == 0
              and (harness.captures / "sleep-calls.txt").read_text(encoding="utf-8").split()
              == ["2", "4", "8"],
              ((harness.captures / "sleep-calls.txt").read_text(encoding="utf-8")
               if (harness.captures / "sleep-calls.txt").is_file() else None))
        harness = LaunchHarness(root / "remote-failure")
        harness.ssh_answers([1])
        result = harness.run(["seat-p"])
        check("a remote command failure (not 255) ends the launcher with that status, no retry",
              result["launched"].returncode == 1 and harness.count("ssh-calls.txt") == 1
              and "retrying" not in result["launched"].stderr,
              (result["launched"].returncode, harness.count("ssh-calls.txt")))
        harness = LaunchHarness(root / "detached-no-retry")
        harness.ssh_answers([255, 0])
        result = harness.run(["seat-q", "--no-attach"])
        check("a detached launch does not retry: one ssh, exit 255 passed through",
              result["launched"].returncode == 255 and harness.count("ssh-calls.txt") == 1,
              (result["launched"].returncode, harness.count("ssh-calls.txt")))

        # 12. The box-side update runs under the machine-wide lock
        # (user-approved 2026-09-22): an update that finds another holding
        # the lock waits for it, then runs; one held past the limit is
        # skipped with one line, and the seat is still prepared. The lock is
        # held from this process on the sandbox HOME's lock file, the file
        # the box-side helper resolves there.
        harness = LaunchHarness(root / "update-lock-wait")
        harness.update_timeout_seconds = 30
        with AnotherUpdateHoldsTheLock(harness.update_lock_path(),
                                       harness.release_marker,
                                       release_after_seconds=1.5):
            result = harness.run(["seat-u", "--no-attach"])
        check("update lock (box): an update started while another holds the "
              "lock waits, then runs",
              harness.claude_updates() == ["after-release"],
              (harness.claude_updates(), result["replay"].stderr[:400]))
        check("update lock (box): the waiting update says it is waiting",
              "launch-claude-ubuntu: waiting for another update on this "
              "machine to finish" in result["replay"].stderr,
              result["replay"].stderr[:400])
        check("update lock (box): the seat is prepared after the wait",
              result["replay"].returncode == 0 and harness.prepare_ran(),
              (result["replay"].returncode, result["replay"].stderr[:300]))

        harness = LaunchHarness(root / "update-lock-bound")
        harness.update_timeout_seconds = 1
        with AnotherUpdateHoldsTheLock(harness.update_lock_path(),
                                       harness.release_marker):
            started = time.monotonic()
            result = harness.run(["seat-v", "--no-attach"])
            elapsed = time.monotonic() - started
        check("update lock (box): a lock held past the limit skips this update",
              harness.claude_updates() == [], harness.claude_updates())
        check("update lock (box): the skip is reported in one line naming the limit",
              "launch-claude-ubuntu: another update on this machine was still "
              "running after 1s; skipping this update and launching on the "
              "installed version" in result["replay"].stderr,
              result["replay"].stderr[:400])
        check("update lock (box): the seat is still prepared, without hanging",
              result["replay"].returncode == 0 and harness.prepare_ran()
              and elapsed < 15,
              (result["replay"].returncode, f"{elapsed:.1f}s",
               result["replay"].stderr[:300]))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
