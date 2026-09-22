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

The seat-credential cases turn that same layer model on a secret, and they
are why the launcher reads its token file with `IFS= read -r` rather than
`$(cat ...)`. A `$(...)` in the pane command is run at P1, by the box's
login shell, which then hands tmux a string with the token substituted
into it — a `ps` listing on the box carrying the credential for as long as
the seat lives. So absence is asserted against the tmux argv capture, the
pane command as tmux received it AFTER P1, and not against the remote
string the launcher composed: the launcher never holds the value, so the
remote string is clean under either implementation and a case that looked
only there would pass on the leaking one. Presence is asserted against the
supervisor's environment in the same case, so neither half can pass alone.

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
        write_stub(self.stubs, "python3",
                   '{ printf \'%s\\n\' "$@"; echo "=== call boundary ==="; } '
                   '>> "$LCU_TEST_DIR/python3-calls.txt"\n'
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (*handoff-supervisor.py*)\n'
                   '    { echo "CLAUDE_CODE_TASK_LIST_ID='
                   '${CLAUDE_CODE_TASK_LIST_ID-<unset>}";\n'
                   '      echo "CLAUDE_CODE_ENABLE_TODO_TOOLS='
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}";\n'
                   '      echo "GH_TOKEN=${GH_TOKEN-<unset>}"; } '
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
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}";\n'
                   '  echo "GH_TOKEN=${GH_TOKEN-<unset>}"; } '
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
        }
        # This whitelist is what keeps the replay clean, so an ambient
        # GH_TOKEN can only appear here on purpose: it stands in for a box
        # shell that already carries one, which the seat must not keep.
        if self.ambient_gh_token is not None:
            environment["GH_TOKEN"] = self.ambient_gh_token
        return environment

    unit_state = "inactive"
    ambient_gh_token = None

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

    def write_seat_token(self, account: str, token: str,
                         trailing_newline: bool = True) -> Path:
        """Put a token file for one account in the sandbox HOME, which stands
        in for the BOX's home: the launcher composes ~/.config/nedschorus/,
        and P1 resolves that ~ against this HOME. Never a real credential —
        the value is the thing the cases hunt for in the post-P1 command, so
        it has to be a string this suite invented."""
        token_file = self.home / ".config" / "nedschorus" / f"{account}.token"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token + ("\n" if trailing_newline else ""),
                              encoding="utf-8")
        token_file.chmod(0o600)
        return token_file

    def run(self, launcher_arguments, agents_root=None, extra_arguments=None,
            seat_github_account=None):
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
        if seat_github_account is not None:
            environment["NEDSCHORUS_SEAT_GITHUB_ACCOUNT"] = seat_github_account
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
        tmux_argv_capture = self.captures / "tmux-argv.txt"
        return {
            "launched": launched,
            "remote": remote,
            "replay": replayed,
            # The pane command as tmux received it, AFTER P1 — the only
            # place a P1-substituted secret would show.
            "tmux_argv": (tmux_argv_capture.read_text(encoding="utf-8")
                          if tmux_argv_capture.is_file() else ""),
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

        # --- 12. the seat's own GitHub credential (credential ruling C4,
        # nc-systems/main-gatekeeper/main-gatekeeper-design.md: each agent
        # host holds a fine-grained token for this repository only, never a
        # classic all-repository token and never the `workflow` scope).
        # Measured on the box 2026-09-22: `gh` is logged in as
        # `ubuntu-claude` — the right identity — but with a CLASSIC token
        # carrying read:org, repo and workflow, and no `ubuntu-claude.token`
        # file exists on the box at all. The default account here is the
        # BOX's.
        seat_token = "github_pat_UBUNTU_CLAUDE_TEST_ONLY_not-a-real-credential"
        harness = LaunchHarness(root / "seat-token-present")
        harness.write_seat_token("ubuntu-claude", seat_token)
        result = harness.run(["seat-r1", "--no-attach"])
        check("seat token: the default account is the BOX's, and its token "
              "reaches the box-side supervisor's environment",
              result["replay"].returncode == 0
              and result["supervisor_environment"].get("GH_TOKEN") == seat_token,
              (result["replay"].returncode,
               result["supervisor_environment"].get("GH_TOKEN"),
               result["replay"].stderr[:300]))

        # The property the read-not-substitute shape exists for, asserted
        # where it can actually fail: the tmux argv capture is the pane
        # command AFTER the box shell parsed it at P1, so a `$(cat ...)`
        # that P1 ran would show the token there. The remote string the
        # launcher composed is checked too, but it proves less — the
        # launcher never holds the value — so the two are asserted together
        # with the environment half, and no one of them passes alone.
        check("seat token: the token text is ABSENT from the pane command "
              "tmux received (post-P1), present only in the environment",
              seat_token not in result["tmux_argv"]
              and seat_token not in result["remote"]
              and seat_token not in result["replay"].stdout
              and seat_token not in result["replay"].stderr
              and result["supervisor_environment"].get("GH_TOKEN") == seat_token,
              ("token in the post-P1 pane command"
               if seat_token in result["tmux_argv"] else
               "token in the remote string" if seat_token in result["remote"]
               else "token in the replay output"
               if (seat_token in result["replay"].stdout
                   or seat_token in result["replay"].stderr)
               else result["supervisor_environment"].get("GH_TOKEN")))
        # The other half of the same property: the pane command names the
        # token FILE and exports GH_TOKEN from it, so the read happens in the
        # seat's own shell on the box. Without this, a launcher that simply
        # never exported anything would satisfy the absence case above.
        check("seat token: the pane command names the box-side token file and "
              "defers the read to the seat's own shell",
              ".config/nedschorus/ubuntu-claude.token" in result["tmux_argv"]
              and "GH_TOKEN" in result["tmux_argv"],
              result["tmux_argv"][:400])

        # --- 13. no token file on the box — the box's state today. GH_TOKEN
        # stays UNSET rather than empty (`gh` falls back to its keyring login
        # on an unset variable and fails outright on an empty one), the
        # launch still happens, and the warning comes back down the ssh
        # connection because it rides the PREPARE step rather than the pane
        # command: a pane-command warning would land in the seat's tmux pane,
        # which a detached launch leaves nobody watching.
        harness = LaunchHarness(root / "seat-token-absent")
        result = harness.run(["seat-r2", "--no-attach"])
        check("no seat token: the launch still happens (warn, never refuse)",
              result["launched"].returncode == 0
              and result["replay"].returncode == 0
              and "handoff-supervisor.py" in " ".join(result["supervisor_argv"]),
              (result["launched"].returncode, result["replay"].returncode,
               result["replay"].stderr[:300]))
        check("no seat token: GH_TOKEN is UNSET in the supervisor's environment",
              result["supervisor_environment"].get("GH_TOKEN") == "<unset>",
              result["supervisor_environment"])
        check("no seat token: the warning comes back over the connection, "
              "naming the account, the box-side path and the fallback",
              "ubuntu-claude" in result["replay"].stderr
              and f"{harness.home}/.config/nedschorus/ubuntu-claude.token"
              in result["replay"].stderr
              and "GH_TOKEN stays unset" in result["replay"].stderr
              and "keyring" in result["replay"].stderr,
              result["replay"].stderr[-900:])

        # --- 14. the override, and the ruling it inherits: an override
        # either works or is blocked, never a third state (user-ruled
        # 2026-08-22). Both accounts hold a token file, so the case measures
        # a CHOICE rather than the only file present.
        merge_token = "github_pat_NED_REVIEW_MERGE_TEST_ONLY_not-a-real-credential"
        harness = LaunchHarness(root / "seat-token-override")
        harness.write_seat_token("ubuntu-claude", seat_token)
        harness.write_seat_token("ned-review-merge", merge_token)
        result = harness.run(["seat-r3", "--no-attach"],
                             seat_github_account="ned-review-merge")
        check("override: the named account's token is the one exported, not "
              "the host default's",
              result["replay"].returncode == 0
              and result["supervisor_environment"].get("GH_TOKEN") == merge_token,
              (result["replay"].returncode,
               result["supervisor_environment"].get("GH_TOKEN")))
        check("override: neither token text reaches the post-P1 pane command",
              merge_token not in result["tmux_argv"]
              and seat_token not in result["tmux_argv"],
              result["tmux_argv"][:400])

        harness = LaunchHarness(root / "seat-account-refused")
        result = harness.run(["seat-r4", "--no-attach"],
                             seat_github_account="../../etc/passwd")
        check("bad override: refused with exit 2, naming what the value is",
              result["launched"].returncode == 2
              and "NEDSCHORUS_SEAT_GITHUB_ACCOUNT" in result["launched"].stderr
              and "GitHub account name" in result["launched"].stderr,
              (result["launched"].returncode,
               result["launched"].stderr[:300]))
        check("bad override: nothing was sent to the box",
              result["remote"] == "", result["remote"][:200])

        # --- 15. the after-exit shell inherits the credential, as it
        # inherits the task-list pin and for the same reason: the
        # `claude --continue` that shell offers is the same seat.
        harness = LaunchHarness(root / "seat-token-attached")
        harness.write_seat_token("ubuntu-claude", seat_token)
        result = harness.run(["seat-r5"])
        check("attached: the supervisor still gets the seat's token",
              result["replay"].returncode == 0
              and result["supervisor_environment"].get("GH_TOKEN") == seat_token,
              (result["replay"].returncode,
               result["supervisor_environment"].get("GH_TOKEN")))
        check("attached: the after-exit shell keeps the seat's credential",
              result["after_exit_environment"].get("GH_TOKEN") == seat_token,
              result["after_exit_environment"].get("GH_TOKEN"))

        # --- 16. an inherited GH_TOKEN is DROPPED box-side, not kept: the
        # seat's account is decided by this launcher and never inherited
        # from the shell the pane was started under, or the prepare step's
        # warning would announce a fallback that did not happen.
        inherited_token = "github_pat_INHERITED_TEST_ONLY_not-a-real-credential"
        harness = LaunchHarness(root / "seat-token-ambient-dropped")
        harness.ambient_gh_token = inherited_token
        result = harness.run(["seat-r6", "--no-attach"])
        check("no seat token: an inherited GH_TOKEN is dropped, not passed on",
              result["replay"].returncode == 0
              and result["supervisor_environment"].get("GH_TOKEN") == "<unset>",
              result["supervisor_environment"].get("GH_TOKEN"))

        # --- 17. the real token files carry NO trailing newline (measured
        # 2026-09-22: 93 bytes, `tail -c1 | wc -l` reports 0). `read` returns
        # non-zero on such a file AFTER setting the variable, so the value
        # must still arrive whole through both parses.
        harness = LaunchHarness(root / "seat-token-no-trailing-newline")
        harness.write_seat_token("ubuntu-claude", seat_token,
                                 trailing_newline=False)
        result = harness.run(["seat-r7", "--no-attach"])
        check("seat token: a file with no trailing newline still yields the "
              "whole token",
              result["replay"].returncode == 0
              and result["supervisor_environment"].get("GH_TOKEN") == seat_token,
              (result["replay"].returncode,
               result["supervisor_environment"].get("GH_TOKEN")))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
