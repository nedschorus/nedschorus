#!/usr/bin/env python3
"""Tests for launch-claude-mac's agents-root tilde handling.

The rule (PR #137 review P3, user-ruled 2026-08-22): an override either
works or is blocked, never a third state. A literal-tilde
NEDSCHORUS_AGENTS_ROOT (a quoted export sends one) used to half-work — this
launcher would mkdir a literal ~ directory while every fleet Python tool
expanduser()s the same value, splitting the seat across two directories.
Now ~/ resolves to $HOME exactly as the operator's shell would have made
it, and ~user/ is refused outright before any side effect.

EVERY case runs the real launcher inside a sandbox — recording stubs for
tmux/claude/python3/git on PATH, throwaway HOME, throwaway working
directory (PR #139 review finding A: an unsandboxed refusal case performs
the very side effects it exists to prove absent on the day the guard
regresses — against a pre-guard launcher it ran `claude update`, wrote
real trust into ~/.claude.json, and started a real seat). "Refused before
any side effect" is asserted as measured facts: no stub was invoked and
no directory was created, not a stdout proxy.

Run: python3 scripts/launch-claude-mac-test.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

LAUNCHER = Path(__file__).with_name("launch-claude-mac")

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


class MacLaunchSandbox:
    """A per-case sandbox: recording stubs, throwaway HOME and cwd."""

    def __init__(self, root: Path):
        self.home = root / "home"
        self.home.mkdir(parents=True)
        self.workdir = root / "workdir"
        self.workdir.mkdir()
        self.captures = root / "captures"
        self.captures.mkdir()
        self.stubs = root / "stubs"
        self.stubs.mkdir()
        record = f'echo "$0" >> "{self.captures}/commands-invoked.txt"\n'
        write_stub(self.stubs, "tmux",
                   record +
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (has-session) exit 1;; esac\n'
                   'done\n'
                   f'printf \'%s\\n\' "$@" > "{self.captures}/tmux-argv.txt"\n'
                   'exit 0\n')
        for stub_name in ("claude", "python3", "git"):
            write_stub(self.stubs, stub_name, record + "exit 0\n")

    def run(self, agents_root):
        return subprocess.run(
            [str(LAUNCHER), "seat-t", "--no-attach"],
            capture_output=True, text=True, check=False,
            cwd=str(self.workdir),
            env={**{key: value for key, value in os.environ.items()
                    if not key.startswith(("NEDSCHORUS_", "LAUNCH_CLAUDE_"))},
                 "NEDSCHORUS_AGENTS_ROOT": agents_root,
                 "HOME": str(self.home),
                 "PATH": f"{self.stubs}:/usr/bin:/bin:/usr/sbin:/sbin"})

    def invoked_commands(self):
        path = self.captures / "commands-invoked.txt"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def tmux_argv(self):
        path = self.captures / "tmux-argv.txt"
        return (path.read_text(encoding="utf-8").splitlines()
                if path.is_file() else [])


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="launch-claude-mac-test-") as scratch:
        root = Path(scratch)

        # --- ~user root: refused before anything runs ----------------------
        sandbox = MacLaunchSandbox(root / "tilde-user")
        result = sandbox.run("~alice/agents")
        check("tilde-user root: refused with exit 2, naming the split",
              result.returncode == 2 and "not supported" in result.stderr
              and "splitting the seat" in result.stderr,
              (result.returncode, result.stderr[:200]))
        check("tilde-user root: no command was invoked",
              sandbox.invoked_commands() == "",
              sandbox.invoked_commands()[:200])
        check("tilde-user root: no directory was created",
              not any(sandbox.workdir.iterdir())
              and not any(sandbox.home.iterdir()),
              (sorted(str(p) for p in sandbox.workdir.iterdir()),
               sorted(str(p) for p in sandbox.home.iterdir())))

        # --- ~/ root: resolved to $HOME, end to end through the launcher ---
        sandbox = MacLaunchSandbox(root / "tilde-slash")
        result = sandbox.run("~/custom agents")
        tmux_argv = sandbox.tmux_argv()
        seat_directory = f"{sandbox.home}/custom agents/seat-t"
        check("~/ root: the launcher runs to its tmux launch (exit 0)",
              result.returncode == 0 and tmux_argv,
              (result.returncode, result.stderr[:300]))
        check("~/ root: tmux -c is the $HOME-resolved seat directory",
              any(previous == "-c" and current == seat_directory
                  for previous, current in zip(tmux_argv, tmux_argv[1:])),
              tmux_argv)
        check("~/ root: the seat directory was created where resolved",
              Path(seat_directory).is_dir(), seat_directory)
        check("~/ root: nothing leaked into the working directory",
              not any(sandbox.workdir.iterdir()),
              sorted(str(p) for p in sandbox.workdir.iterdir()))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
