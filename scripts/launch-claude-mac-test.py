#!/usr/bin/env python3
"""Tests for launch-claude-mac's agents-root tilde handling.

The rule (PR #137 review P3, user-ruled 2026-08-22): an override either
works or is blocked, never a third state. A literal-tilde
NEDSCHORUS_AGENTS_ROOT (a quoted export sends one) used to half-work — this
launcher would mkdir a literal ~ directory while every fleet Python tool
expanduser()s the same value, splitting the seat across two directories.
Now ~/ resolves to $HOME exactly as the operator's shell would have made
it, and ~user/ is refused outright before any side effect.

The resolution case runs the REAL launcher inside the sandbox recipe the
quoting arc established: stub tmux capturing argv, no-op claude/python3/git
on PATH (the git stub keeps the launcher's worktree and freshness boot
steps away from the real repo), throwaway HOME. The refusal case needs no
stubs at all — the guard sits before every prerequisite check.

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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="launch-claude-mac-test-") as scratch:
        root = Path(scratch)
        base_environment = {key: value for key, value in os.environ.items()
                            if not key.startswith(("NEDSCHORUS_",
                                                   "LAUNCH_CLAUDE_"))}

        # --- ~user root: refused before anything runs ----------------------
        result = subprocess.run(
            [str(LAUNCHER), "seat-u", "--no-attach"],
            capture_output=True, text=True, check=False,
            env={**base_environment,
                 "NEDSCHORUS_AGENTS_ROOT": "~alice/agents"})
        check("tilde-user root: refused with exit 2, naming the split",
              result.returncode == 2 and "not supported" in result.stderr
              and "splitting the seat" in result.stderr,
              (result.returncode, result.stderr[:200]))
        check("tilde-user root: refused before any side effect (silent stdout)",
              result.stdout == "", result.stdout[:200])

        # --- ~/ root: resolved to $HOME, end to end through the launcher ---
        home = root / "home"
        home.mkdir()
        stubs = root / "stubs"
        stubs.mkdir()
        captures = root / "captures"
        captures.mkdir()
        write_stub(stubs, "tmux",
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (has-session) exit 1;; esac\n'
                   'done\n'
                   f'printf \'%s\\n\' "$@" > "{captures}/tmux-argv.txt"\n'
                   'exit 0\n')
        for stub_name in ("claude", "python3", "git"):
            write_stub(stubs, stub_name, "exit 0\n")
        result = subprocess.run(
            [str(LAUNCHER), "seat-t", "--no-attach"],
            capture_output=True, text=True, check=False,
            env={**base_environment,
                 "NEDSCHORUS_AGENTS_ROOT": "~/custom agents",
                 "HOME": str(home),
                 "PATH": f"{stubs}:/usr/bin:/bin:/usr/sbin:/sbin"})
        tmux_argv_path = captures / "tmux-argv.txt"
        tmux_argv = (tmux_argv_path.read_text(encoding="utf-8").splitlines()
                     if tmux_argv_path.is_file() else [])
        seat_directory = f"{home}/custom agents/seat-t"
        check("~/ root: the launcher runs to its tmux launch (exit 0)",
              result.returncode == 0 and tmux_argv,
              (result.returncode, result.stderr[:300]))
        check("~/ root: tmux -c is the $HOME-resolved seat directory",
              any(previous == "-c" and current == seat_directory
                  for previous, current in zip(tmux_argv, tmux_argv[1:])),
              tmux_argv)
        check("~/ root: the seat directory was created where resolved",
              Path(seat_directory).is_dir(), seat_directory)

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
