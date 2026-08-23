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

The suite is self-contained (this file plus launch-claude-ubuntu beside it;
every other participant is stubbed) and runs unmodified ON THE BOX, where
P1 is parsed by the real /bin/sh (dash) instead of macOS sh standing in —
the one caveat the PR #137/#139 reviews carried (user-directed 2026-08-22):
  scp scripts/launch-claude-ubuntu scripts/launch-claude-ubuntu-test.py ned:/tmp/x/
  ssh ned 'cd /tmp/x && chmod +x launch-claude-ubuntu && python3 launch-claude-ubuntu-test.py'
"""

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

LAUNCHER = Path(__file__).with_name("launch-claude-ubuntu")

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
        write_stub(self.stubs, "ssh",
                   'printf \'%s\\n\' "$@" > "$LCU_TEST_DIR/ssh-argv.txt"\n'
                   'exit 0\n')
        write_stub(self.stubs, "timeout", "exit 0\n")
        write_stub(self.stubs, "git", "exit 0\n")
        # The supervisor call also records its ENVIRONMENT, not just its argv:
        # the task-list binding is an exported variable, so the only place it
        # can be measured is the environment of the process the pane command
        # actually starts.
        write_stub(self.stubs, "python3",
                   '{ printf \'%s\\n\' "$@"; echo "=== call boundary ==="; } '
                   '>> "$LCU_TEST_DIR/python3-calls.txt"\n'
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
        return {
            "PATH": f"{self.stubs}:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(self.home),
            "SHELL": str(self.stubs / "record-shell"),
            "LCU_TEST_DIR": str(self.captures),
        }

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
              == f"{harness.home}/Projects/nedschorus/scripts/handoff-supervisor.py",
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
        check("task list: the pin reaches the supervisor as <seat>-tasks",
              result["supervisor_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "seat-h-tasks",
              result["supervisor_environment"])
        check("task list: the task tools are enabled for the supervisor",
              result["supervisor_environment"].get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              result["supervisor_environment"])
        harness = LaunchHarness(root / "task-list-second-seat")
        result = harness.run(["seat-i", "--no-attach"])
        check("task list: a second seat name yields a DIFFERENT list id",
              result["supervisor_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "seat-i-tasks",
              result["supervisor_environment"])

        # --- 9. the same binding on the ATTACHED path, including the
        # after-exit shell: that shell offers `claude --continue`, and a
        # continue run without the pin binds to a session-keyed store whose
        # TaskList returns empty with no error.
        harness = LaunchHarness(root / "task-list-attached")
        result = harness.run(["seat-j"])
        check("task list (attached): the supervisor gets <seat>-tasks",
              result["supervisor_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "seat-j-tasks"
              and result["supervisor_environment"].get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              result["supervisor_environment"])
        check("task list (attached): the after-exit shell keeps the binding",
              result["after_exit_environment"].get("CLAUDE_CODE_TASK_LIST_ID")
              == "seat-j-tasks"
              and result["after_exit_environment"].get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              result["after_exit_environment"])

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
