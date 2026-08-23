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
        self.stubs = root / "stubs"
        self.stubs.mkdir()
        write_stub(self.stubs, "ssh",
                   'printf \'%s\\n\' "$@" > "$LCU_TEST_DIR/ssh-argv.txt"\n'
                   'exit 0\n')
        write_stub(self.stubs, "timeout", "exit 0\n")
        write_stub(self.stubs, "git", "exit 0\n")
        write_stub(self.stubs, "python3",
                   '{ printf \'%s\\n\' "$@"; echo "=== call boundary ==="; } '
                   '>> "$LCU_TEST_DIR/python3-calls.txt"\n'
                   'exit 0\n')
        # The attached pane ends in `exec $SHELL`; this stand-in records the
        # directory that shell would start in — the after-exit cd's actual
        # landing point, which exit codes alone cannot pin (a failed cd is
        # followed by an exec that succeeds anyway).
        write_stub(self.stubs, "record-shell",
                   'pwd > "$LCU_TEST_DIR/after-exit-cwd.txt"\n')
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
            capture_output=True, text=True, check=False, env=environment)
        ssh_capture = self.captures / "ssh-argv.txt"
        remote = (ssh_capture.read_text(encoding="utf-8").splitlines()[-1]
                  if ssh_capture.is_file() else "")
        replayed = subprocess.run(
            ["/bin/sh", "-c", remote], capture_output=True, text=True,
            check=False, env=self.replay_environment())
        pane_directory_capture = self.captures / "tmux-pane-directory.txt"
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
        }


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

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
