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
ambient value rather than the composed one. GH_TOKEN is stripped for the
same reason and it is the sharper case: the merge-lane seat exports its
own token by hand today, so a suite run from there would see GH_TOKEN in
the supervisor's environment whether or not the launcher put it there —
the token-present case passing on the runner's credential, and the
token-absent case failing for a reason that has nothing to do with the
launcher.

The credential cases carry one assertion the others do not need: that the
token's TEXT is absent from the composed command. tmux is handed that
string, so a token spliced into it stands in every `ps` listing on the
machine for as long as the seat lives. Absence is asserted against the
tmux argv capture — the command as tmux received it — and presence against
the supervisor's environment, in the same case, so neither half can pass
alone.

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
        # The supervisor call records its ENVIRONMENT and its argv as well
        # as the fact that it ran. The extra-arguments hook variable is
        # recorded too: it must reach the supervisor as ARGUMENTS and never
        # as an inherited variable (the 2026-09-03 resume leak, below).
        write_stub(self.stubs, "python3",
                   record +
                   'for argument in "$@"; do\n'
                   '  case "$argument" in (*handoff-supervisor.py*)\n'
                   f'    printf \'%s\\n\' "$@" > "{self.captures}/supervisor-argv.txt"\n'
                   '    { echo "CLAUDE_CODE_TASK_LIST_ID='
                   '${CLAUDE_CODE_TASK_LIST_ID-<unset>}";\n'
                   '      echo "CLAUDE_CODE_ENABLE_TODO_TOOLS='
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}";\n'
                   '      echo "GH_TOKEN=${GH_TOKEN-<unset>}";\n'
                   '      echo "NEDSCHORUS_SEAT_GITHUB_ACCOUNT='
                   '${NEDSCHORUS_SEAT_GITHUB_ACCOUNT-<unset>}";\n'
                   '      echo "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS='
                   '${LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS-<unset>}"; } '
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
                   '${CLAUDE_CODE_ENABLE_TODO_TOOLS-<unset>}";\n'
                   '  echo "GH_TOKEN=${GH_TOKEN-<unset>}";\n'
                   '  echo "NEDSCHORUS_SEAT_GITHUB_ACCOUNT='
                   '${NEDSCHORUS_SEAT_GITHUB_ACCOUNT-<unset>}";\n'
                   '  echo "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS='
                   '${LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS-<unset>}"; } '
                   f'> "{self.captures}/after-exit-environment.txt"\n')

    def write_seat_token(self, account: str, token: str,
                         trailing_newline: bool = True) -> Path:
        """Put a token file for one account in the sandbox HOME, where the
        launcher looks. Never a real credential: the value is the thing the
        cases hunt for in the composed command, so it has to be a string
        this suite invented."""
        token_file = self.home / ".config" / "nedschorus" / f"{account}.token"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token + ("\n" if trailing_newline else ""),
                              encoding="utf-8")
        token_file.chmod(0o600)
        return token_file

    def run(self, agents_root, seat_name="seat-t", attach=False,
            extra_arguments=None, seat_github_account=None,
            ambient_gh_token=None):
        """Run the launcher in the sandbox. extra_arguments, when given, is
        placed in LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS the way
        recover-crashed-seats.py's launch_seat places it — after the strip
        of ambient LAUNCH_CLAUDE_* values, so the case measures its own.
        seat_github_account rides NEDSCHORUS_SEAT_GITHUB_ACCOUNT the same
        way, after the strip of ambient NEDSCHORUS_* values.
        ambient_gh_token puts a GH_TOKEN in the launcher's environment after
        the strip, standing in for the shell of a seat that already exports
        one — which the merge-lane seat does by hand today."""
        arguments = [seat_name] if attach else [seat_name, "--no-attach"]
        environment = {
            **{key: value for key, value in os.environ.items()
               if key != "GH_TOKEN"
               and not key.startswith(("NEDSCHORUS_", "LAUNCH_CLAUDE_",
                                       "CLAUDE_CODE_"))},
            "NEDSCHORUS_AGENTS_ROOT": agents_root,
            "HOME": str(self.home),
            "SHELL": str(self.stubs / "record-shell"),
            "PATH": f"{self.stubs}:/usr/bin:/bin:/usr/sbin:/sbin"}
        if extra_arguments is not None:
            environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = extra_arguments
        if seat_github_account is not None:
            environment["NEDSCHORUS_SEAT_GITHUB_ACCOUNT"] = seat_github_account
        if ambient_gh_token is not None:
            environment["GH_TOKEN"] = ambient_gh_token
        return subprocess.run(
            [str(LAUNCHER), *arguments],
            capture_output=True, text=True, check=False,
            cwd=str(self.workdir), env=environment)

    def invoked_commands(self):
        path = self.captures / "commands-invoked.txt"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def tmux_argv(self):
        path = self.captures / "tmux-argv.txt"
        return (path.read_text(encoding="utf-8").splitlines()
                if path.is_file() else [])

    def supervisor_environment(self):
        return environment_lines(self.captures / "supervisor-environment.txt")

    def supervisor_argv(self):
        path = self.captures / "supervisor-argv.txt"
        return (path.read_text(encoding="utf-8").splitlines()
                if path.is_file() else [])

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

        # --- the update step resolves the SEAT's claude, not the ambient one
        # The launcher exports ~/.local/bin ahead of the inherited PATH before
        # it checks for or updates Claude Code, so the copy it updates is the
        # copy the seat will run. Measured 2026-08-31: without that export the
        # Mac's update step reached a Homebrew-installed claude while its seats
        # ran the native build, and the machine sat a week behind with every
        # launch looking normal. Asserted on WHICH binary ran, not on the
        # command text: the stubs record $0, so the two copies are told apart
        # by the path the shell actually resolved.
        sandbox = MacLaunchSandbox(root / "update-step-path")
        seat_binary_directory = sandbox.home / ".local" / "bin"
        seat_binary_directory.mkdir(parents=True)
        write_stub(seat_binary_directory, "claude",
                   f'echo "$0" >> "{sandbox.captures}/commands-invoked.txt"\n'
                   "exit 0\n")
        result = sandbox.run(str(root / "update-step-path-agents"))
        invoked = sandbox.invoked_commands()
        check("update step: the claude under $HOME/.local/bin is the one invoked",
              str(seat_binary_directory / "claude") in invoked, invoked[:400])
        check("update step: the inherited-PATH claude is never reached",
              str(sandbox.stubs / "claude") not in invoked, invoked[:400])
        check("update step: the launch still completes, reaching tmux",
              result.returncode == 0 and sandbox.tmux_argv(),
              (result.returncode, result.stderr[:300]))

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

        # --- the extra-arguments hook is CONSUMED, not inherited. Measured
        # 2026-09-03: recover-crashed-seats.py launched a seat with
        # LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS="--handoff-dir …
        # --resume-session-id <id>"; the launcher folded that into the
        # supervisor command and then started the seat's tmux server with
        # the variable still set, so the server, the supervisor and the
        # recovered claude session all inherited it. When an agent in that
        # session ran `launch-claude-mac <other-seat>` from its Bash tool,
        # the launcher found the inherited value and gave the OTHER seat
        # `--resume-session-id <the recovering session's id>`: a
        # `claude --resume` of the first seat's session came up in the
        # second seat's directory and appended 71+ wrong-cwd records to the
        # first seat's transcript before it was killed by hand. Two halves,
        # both required: the arguments still reach the supervisor's argv
        # (the hook works), and the variable is absent from the supervisor's
        # environment (the seat cannot pass it on). ---------------------------
        recovery_extra_arguments = (
            f"--handoff-dir {root / 'handoffs'} "
            "--resume-session-id ee460522-0000-4000-8000-000000000000")
        sandbox = MacLaunchSandbox(root / "hook-consumed-detached")
        result = sandbox.run("~/agents", seat_name="seat-r",
                             extra_arguments=recovery_extra_arguments)
        supervisor_argv = sandbox.supervisor_argv()
        check("hook (detached): the extra arguments reach the supervisor's argv",
              result.returncode == 0
              and "--resume-session-id" in supervisor_argv
              and supervisor_argv[-1] == "ee460522-0000-4000-8000-000000000000"
              and "--handoff-dir" in supervisor_argv,
              (result.returncode, supervisor_argv, result.stderr[:300]))
        check("hook (detached): the supervisor does NOT inherit the hook variable",
              sandbox.supervisor_environment().get(
                  "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS") == "<unset>",
              sandbox.supervisor_environment())

        sandbox = MacLaunchSandbox(root / "hook-consumed-attached")
        result = sandbox.run("~/agents", seat_name="seat-s", attach=True,
                             extra_arguments=recovery_extra_arguments)
        supervisor_argv = sandbox.supervisor_argv()
        check("hook (attached): the extra arguments reach the supervisor's argv",
              result.returncode == 0
              and "--resume-session-id" in supervisor_argv
              and supervisor_argv[-1] == "ee460522-0000-4000-8000-000000000000",
              (result.returncode, supervisor_argv, result.stderr[:300]))
        check("hook (attached): the supervisor does NOT inherit the hook variable",
              sandbox.supervisor_environment().get(
                  "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS") == "<unset>",
              sandbox.supervisor_environment())
        # The after-exit shell is where an operator types the next
        # `launch-claude-mac <other-seat>`; it must not carry it either.
        check("hook (attached): the after-exit shell does NOT inherit the hook variable",
              sandbox.after_exit_environment().get(
                  "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS") == "<unset>",
              sandbox.after_exit_environment())

        # --- the seat's own GitHub credential (credential ruling C4,
        # nc-systems/main-gatekeeper/main-gatekeeper-design.md: each agent
        # host holds a fine-grained token for this repository only). Measured
        # on this Mac 2026-09-22, and the reason these cases exist: `gh auth
        # status` reported the login as `nedlern` — the USER — with a classic
        # token carrying admin:enterprise, admin:org, repo, workflow and
        # user, so every Mac seat ran with the owner's organization-admin
        # credential and no server-side record could tell a seat from him.
        # The default account is the HOST's, `mac-claude`.
        seat_token = "github_pat_MAC_CLAUDE_TEST_ONLY_not-a-real-credential"
        sandbox = MacLaunchSandbox(root / "seat-token-present")
        sandbox.write_seat_token("mac-claude", seat_token)
        result = sandbox.run("~/agents", seat_name="seat-t1")
        check("seat token: the default account is the HOST's, and its token "
              "reaches the supervisor's environment",
              result.returncode == 0
              and sandbox.supervisor_environment().get("GH_TOKEN") == seat_token,
              (result.returncode,
               sandbox.supervisor_environment().get("GH_TOKEN"),
               result.stderr[:300]))

        # The property the whole shape exists for: tmux is handed the
        # composed string, so a token spliced into it would stand in every
        # `ps` listing on this machine for as long as the seat lives. The
        # composed string must carry the READ and not the value — and the
        # same case asserts the value IS in the environment, so neither half
        # can pass alone (a launcher that exported nothing would satisfy the
        # absence half by itself).
        composed_command = "\n".join(sandbox.tmux_argv())
        check("seat token: the token text is ABSENT from the composed command, "
              "present only in the environment",
              seat_token not in composed_command
              and seat_token not in result.stdout
              and seat_token not in result.stderr
              and sandbox.supervisor_environment().get("GH_TOKEN") == seat_token,
              ("token in tmux argv" if seat_token in composed_command else
               "token in launcher output" if (seat_token in result.stdout
                                              or seat_token in result.stderr)
               else sandbox.supervisor_environment().get("GH_TOKEN")))
        # The other half of the same property: the composed command names the
        # token FILE and exports GH_TOKEN from it, so the read is deferred to
        # the seat's own shell rather than done here. Without this, a
        # launcher that simply never exported anything would satisfy the
        # absence case above.
        check("seat token: the composed command names the token file and "
              "defers the read to the seat's own shell",
              ".config/nedschorus/mac-claude.token" in composed_command
              and "GH_TOKEN" in composed_command,
              composed_command[:400])

        # --- no token file: GH_TOKEN stays UNSET, not empty (gh falls back
        # to its keyring login on an unset variable and fails outright on an
        # empty one), and the launcher says so loudly rather than refusing.
        # Refusing was rejected by the user 2026-09-22: the box holds no
        # `ubuntu-claude.token` today, so a hard failure would take every
        # seat on both machines down over a credential that is an
        # improvement, not a prerequisite.
        sandbox = MacLaunchSandbox(root / "seat-token-absent")
        result = sandbox.run("~/agents", seat_name="seat-t2")
        check("no seat token: the launch still happens (warn, never refuse)",
              result.returncode == 0 and sandbox.tmux_argv(),
              (result.returncode, result.stderr[:300]))
        check("no seat token: GH_TOKEN is UNSET in the supervisor's environment",
              sandbox.supervisor_environment().get("GH_TOKEN") == "<unset>",
              sandbox.supervisor_environment())
        check("no seat token: the warning names the account, the path it "
              "looked in, and the fallback",
              "mac-claude" in result.stderr
              and f"{sandbox.home}/.config/nedschorus/mac-claude.token"
              in result.stderr
              and "GH_TOKEN stays unset" in result.stderr
              and "keyring" in result.stderr,
              result.stderr[-900:])

        # --- the override: a seat whose job needs a different identity.
        # The merge-lane seat must be `ned-review-merge`, because that is the
        # account main's protection lets merge and GitHub refuses an
        # approving review from a pull request's author
        # (docs/nedschorus-wiki/queue/github-identities-credentials-and-token-policy.md).
        # Both accounts hold a token file here, so the case measures a
        # CHOICE rather than the only file present.
        merge_token = "github_pat_NED_REVIEW_MERGE_TEST_ONLY_not-a-real-credential"
        sandbox = MacLaunchSandbox(root / "seat-token-override")
        sandbox.write_seat_token("mac-claude", seat_token)
        sandbox.write_seat_token("ned-review-merge", merge_token)
        result = sandbox.run("~/agents", seat_name="seat-t3",
                             seat_github_account="ned-review-merge")
        check("override: the named account's token is the one exported, not "
              "the host default's",
              result.returncode == 0
              and sandbox.supervisor_environment().get("GH_TOKEN") == merge_token,
              (result.returncode,
               sandbox.supervisor_environment().get("GH_TOKEN")))
        check("override: that token is absent from the composed command too",
              merge_token not in "\n".join(sandbox.tmux_argv())
              and seat_token not in "\n".join(sandbox.tmux_argv()),
              "\n".join(sandbox.tmux_argv())[:400])
        # The override is CONSUMED, never inherited — the 2026-09-03 leak
        # class, applied to a variable where it is sharper. The merge-lane
        # seat is launched with the override set to `ned-review-merge`, an
        # account on main's push allow-list; an inherited value would give
        # every seat merge-lane launches from its own Bash tool that same
        # account, which is a second merge lane. Measured in the environment
        # the seat's tree actually gets, both halves: the supervisor, and the
        # after-exit shell where an operator types the next launch.
        check("override: the supervisor does NOT inherit the override variable",
              sandbox.supervisor_environment().get(
                  "NEDSCHORUS_SEAT_GITHUB_ACCOUNT") == "<unset>",
              sandbox.supervisor_environment())

        sandbox = MacLaunchSandbox(root / "seat-account-not-inherited")
        sandbox.write_seat_token("mac-claude", seat_token)
        sandbox.write_seat_token("ned-review-merge", merge_token)
        result = sandbox.run("~/agents", seat_name="seat-t6", attach=True,
                             seat_github_account="ned-review-merge")
        check("override (attached): neither the supervisor nor the after-exit "
              "shell inherits the override variable",
              result.returncode == 0
              and sandbox.supervisor_environment().get(
                  "NEDSCHORUS_SEAT_GITHUB_ACCOUNT") == "<unset>"
              and sandbox.after_exit_environment().get(
                  "NEDSCHORUS_SEAT_GITHUB_ACCOUNT") == "<unset>",
              (sandbox.supervisor_environment().get(
                  "NEDSCHORUS_SEAT_GITHUB_ACCOUNT"),
               sandbox.after_exit_environment().get(
                   "NEDSCHORUS_SEAT_GITHUB_ACCOUNT")))

        # An override either works or is blocked, never a third state
        # (user-ruled 2026-08-22, the ruling this launcher already cites for
        # NEDSCHORUS_AGENTS_ROOT): a value that is not an account name is
        # refused before any side effect, asserted as measured facts the way
        # the ~user case above is — no stub invoked, no directory created.
        sandbox = MacLaunchSandbox(root / "seat-account-refused")
        result = sandbox.run("~/agents", seat_name="seat-t4",
                             seat_github_account="../../etc/passwd")
        check("bad override: refused with exit 2, naming what the value is",
              result.returncode == 2
              and "NEDSCHORUS_SEAT_GITHUB_ACCOUNT" in result.stderr
              and "GitHub account name" in result.stderr,
              (result.returncode, result.stderr[:300]))
        check("bad override: refused before any side effect",
              sandbox.invoked_commands() == ""
              and not any(sandbox.workdir.iterdir()),
              (sandbox.invoked_commands()[:200],
               sorted(str(p) for p in sandbox.workdir.iterdir())))

        # --- the after-exit shell inherits the credential, as it inherits
        # the task-list pin and for the same reason: the `claude --continue`
        # that shell offers is the same seat, and a `gh` typed there is the
        # seat acting rather than the user. Nothing is re-exported for it —
        # it is the same pane shell.
        sandbox = MacLaunchSandbox(root / "seat-token-attached")
        sandbox.write_seat_token("mac-claude", seat_token)
        result = sandbox.run("~/agents", seat_name="seat-t5", attach=True)
        check("attached: the supervisor still gets the seat's token",
              result.returncode == 0
              and sandbox.supervisor_environment().get("GH_TOKEN") == seat_token,
              (result.returncode,
               sandbox.supervisor_environment().get("GH_TOKEN")))
        check("attached: the after-exit shell keeps the seat's credential",
              sandbox.after_exit_environment().get("GH_TOKEN") == seat_token,
              sandbox.after_exit_environment().get("GH_TOKEN"))

        # --- an inherited GH_TOKEN is DROPPED, not kept. The seat's account
        # is decided by the launcher and never inherited from the shell that
        # started it — the merge-lane seat exports a token by hand today, so
        # a seat it launched would otherwise silently keep merge-lane's
        # credential while the launcher announced a fallback that did not
        # happen. The ambient value is injected after the suite's own strip,
        # so this case measures the launcher and not the suite runner.
        inherited_token = "github_pat_INHERITED_TEST_ONLY_not-a-real-credential"
        sandbox = MacLaunchSandbox(root / "seat-token-ambient-dropped")
        result = sandbox.run("~/agents", seat_name="seat-t7",
                             ambient_gh_token=inherited_token)
        check("no seat token: an inherited GH_TOKEN is dropped, not passed on",
              result.returncode == 0
              and sandbox.supervisor_environment().get("GH_TOKEN") == "<unset>",
              sandbox.supervisor_environment().get("GH_TOKEN"))

        # --- the real token files carry NO trailing newline (measured
        # 2026-09-22: 93 bytes, `tail -c1 | wc -l` reports 0). `read` returns
        # non-zero on that file AFTER setting the variable, so the value must
        # still arrive whole — the case the comment in the launcher asserts
        # and nothing else here exercises, since the other cases write the
        # newline a text editor would add.
        sandbox = MacLaunchSandbox(root / "seat-token-no-trailing-newline")
        sandbox.write_seat_token("mac-claude", seat_token,
                                 trailing_newline=False)
        result = sandbox.run("~/agents", seat_name="seat-t8")
        check("seat token: a file with no trailing newline still yields the "
              "whole token",
              result.returncode == 0
              and sandbox.supervisor_environment().get("GH_TOKEN") == seat_token,
              (result.returncode,
               sandbox.supervisor_environment().get("GH_TOKEN")))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
