#!/usr/bin/env python3
"""Tests for launch-claude-mac: agents-root tilde handling, and the
environment the seat is launched with.

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

The seat-environment cases go one layer further, the way the box twin's
suite does (scripts/launch-claude-ubuntu-test.py): the tmux stub RUNS the
pane command it was handed, through a real sh, and the python3 and
record-shell stubs report the environment of the supervisor and of the
after-exit shell. Environment, not command text — an export can only be
observed in a process started after it, and a case that greps the composed
string would pass on a string that never runs.

The launcher's own CLAUDE_CODE_* variables are stripped alongside
NEDSCHORUS_* and LAUNCH_CLAUDE_*: the launcher runs locally and its
children inherit its environment, so without the strip a suite run from a
seat that already has CLAUDE_CODE_TASK_LIST_ID set would pass on the
ambient value rather than the composed one.

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
        # new-session's pane-command argument is RUN, through a real sh: it
        # is the seat's actual first shell, and the exports the launcher put
        # at its head can only be observed in a process it starts.
        # has-session still answers "no session", so socket selection stays
        # on the per-seat socket and the refusal cases are unaffected —
        # tmux is never reached there at all.
        write_stub(self.stubs, "tmux",
                   record +
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (has-session) exit 1;; esac\n'
                   'done\n'
                   f'printf \'%s\\n\' "$@" > "{self.captures}/tmux-argv.txt"\n'
                   'pane_command=""\n'
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (*handoff-supervisor.py*) '
                   'pane_command=$argument;; esac\n'
                   'done\n'
                   'if [ -n "$pane_command" ]; then sh -c "$pane_command"; fi\n'
                   'exit 0\n')
        # The supervisor call records its ENVIRONMENT as well as the fact
        # that it ran.
        write_stub(self.stubs, "python3",
                   record +
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (*handoff-supervisor.py*)\n'
                   '    { echo "CLAUDE_CODE_TASK_LIST_ID='
                   '${CLAUDE_CODE_TASK_LIST_ID-<unset>}";\n'
                   '      echo "CLAUDE_CODE_ENABLE_TODO_TOOLS='
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}"; } '
                   f'> "{self.captures}/supervisor-environment.txt";;\n'
                   '  esac\n'
                   'done\n'
                   'exit 0\n')
        for stub_name in ("claude", "git"):
            write_stub(self.stubs, stub_name, record + "exit 0\n")
        # An attached pane ends in `exec $SHELL`. This stand-in records where
        # that shell starts and what it inherited — the environment a
        # `claude --continue` typed there would read its task-list binding
        # from.
        write_stub(self.stubs, "record-shell",
                   f'pwd > "{self.captures}/after-exit-cwd.txt"\n'
                   '{ echo "CLAUDE_CODE_TASK_LIST_ID='
                   '${CLAUDE_CODE_TASK_LIST_ID-<unset>}";\n'
                   '  echo "CLAUDE_CODE_ENABLE_TODO_TOOLS='
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}"; } '
                   f'> "{self.captures}/after-exit-environment.txt"\n')

    def run(self, agents_root, seat_name="seat-t", attach=False):
        arguments = [seat_name] if attach else [seat_name, "--no-attach"]
        return subprocess.run(
            [str(LAUNCHER), *arguments],
            capture_output=True, text=True, check=False,
            cwd=str(self.workdir),
            env={**{key: value for key, value in os.environ.items()
                    if not key.startswith(("NEDSCHORUS_", "LAUNCH_CLAUDE_",
                                           "CLAUDE_CODE_"))},
                 "NEDSCHORUS_AGENTS_ROOT": agents_root,
                 "HOME": str(self.home),
                 "SHELL": str(self.stubs / "record-shell"),
                 "PATH": f"{self.stubs}:/usr/bin:/bin:/usr/sbin:/sbin"})

    def invoked_commands(self):
        path = self.captures / "commands-invoked.txt"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def tmux_argv(self):
        path = self.captures / "tmux-argv.txt"
        return (path.read_text(encoding="utf-8").splitlines()
                if path.is_file() else [])

    def supervisor_environment(self):
        return environment_lines(self.captures / "supervisor-environment.txt")

    def after_exit_environment(self):
        return environment_lines(self.captures / "after-exit-environment.txt")

    def after_exit_cwd(self):
        path = self.captures / "after-exit-cwd.txt"
        return (path.read_text(encoding="utf-8").strip()
                if path.is_file() else "")


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

        # --- task-list persistence, detached: both variables reach the
        # supervisor's environment, and the list id is derived from the SEAT
        # NAME. Two different seat names are the teeth: an id arriving from
        # the ambient environment rather than being composed per seat would
        # give both runs the same value. ------------------------------------
        sandbox = MacLaunchSandbox(root / "task-list-detached")
        result = sandbox.run("~/agents", seat_name="seat-a")
        check("detached: the launcher runs to its tmux launch (exit 0)",
              result.returncode == 0 and sandbox.tmux_argv(),
              (result.returncode, result.stderr[:300]))
        check("task list: the pin reaches the supervisor as nedschorus-<seat>-tasks",
              sandbox.supervisor_environment().get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-a-tasks",
              sandbox.supervisor_environment())
        check("task list: the task tools are enabled for the supervisor",
              sandbox.supervisor_environment().get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              sandbox.supervisor_environment())
        # --- task-list migration (user-ruled 2026-08-29): a store filled
        # under the old unprefixed id is renamed to the prefixed id at
        # launch; an existing prefixed store is never overwritten. ----------
        sandbox = MacLaunchSandbox(root / "task-list-migration")
        unprefixed_store = sandbox.home / ".claude" / "tasks" / "seat-m-tasks"
        unprefixed_store.mkdir(parents=True)
        (unprefixed_store / "1.json").write_text('{"id": "1"}',
                                                 encoding="utf-8")
        result = sandbox.run("~/agents", seat_name="seat-m")
        prefixed_store = (sandbox.home / ".claude" / "tasks"
                          / "nedschorus-seat-m-tasks")
        check("migration: the unprefixed store is renamed to the prefixed id",
              result.returncode == 0 and not unprefixed_store.exists()
              and (prefixed_store / "1.json").is_file(),
              (result.returncode,
               sorted(str(p) for p in
                      (sandbox.home / ".claude" / "tasks").glob("*"))))
        sandbox = MacLaunchSandbox(root / "task-list-migration-no-clobber")
        unprefixed_store = sandbox.home / ".claude" / "tasks" / "seat-m-tasks"
        unprefixed_store.mkdir(parents=True)
        (unprefixed_store / "1.json").write_text("unprefixed",
                                                 encoding="utf-8")
        prefixed_store = (sandbox.home / ".claude" / "tasks"
                          / "nedschorus-seat-m-tasks")
        prefixed_store.mkdir(parents=True)
        (prefixed_store / "2.json").write_text("prefixed", encoding="utf-8")
        result = sandbox.run("~/agents", seat_name="seat-m")
        check("migration: an existing prefixed store is never overwritten",
              result.returncode == 0 and unprefixed_store.is_dir()
              and (prefixed_store / "2.json").is_file()
              and not (prefixed_store / "1.json").exists(),
              (result.returncode,
               sorted(str(p) for p in
                      (sandbox.home / ".claude" / "tasks").glob("*"))))

        sandbox = MacLaunchSandbox(root / "task-list-second-seat")
        sandbox.run("~/agents", seat_name="seat-b")
        check("task list: a second seat name yields a DIFFERENT list id",
              sandbox.supervisor_environment().get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-b-tasks",
              sandbox.supervisor_environment())

        # --- the same binding on the ATTACHED path, including the after-exit
        # shell: that shell offers `claude --continue`, and a continue run
        # without the pin binds to a session-keyed store whose TaskList
        # returns empty with no error. ---------------------------------------
        sandbox = MacLaunchSandbox(root / "task-list-attached")
        result = sandbox.run("~/agents", seat_name="seat-c", attach=True)
        check("attached: new-session -A with the wrapper executes to exit 0",
              result.returncode == 0 and "-A" in sandbox.tmux_argv(),
              (result.returncode, result.stderr[:300]))
        check("task list (attached): the supervisor gets nedschorus-<seat>-tasks",
              sandbox.supervisor_environment().get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-c-tasks"
              and sandbox.supervisor_environment().get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              sandbox.supervisor_environment())
        check("task list (attached): the after-exit shell keeps the binding",
              sandbox.after_exit_environment().get("CLAUDE_CODE_TASK_LIST_ID")
              == "nedschorus-seat-c-tasks"
              and sandbox.after_exit_environment().get(
                  "CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1",
              sandbox.after_exit_environment())
        check("attached: the after-exit shell starts in the seat directory",
              # resolve() both sides: macOS reports /var for /private/var
              bool(sandbox.after_exit_cwd())
              and Path(sandbox.after_exit_cwd()).resolve()
              == (sandbox.home / "agents" / "seat-c").resolve(),
              sandbox.after_exit_cwd() or "no shell recorded")

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
