#!/usr/bin/env python3
"""Tests for handoff-supervisor.py: at each session-handoff the supervisor
fast-forwards its own checkout to origin/main and replaces its process with a
fresh start of itself from there, by os.execv.

Covered: where the restart sits in the cycle; that a dont-restart handoff is
not restarted on; that a checkout which cannot fast-forward, or an os.execv
that raises or returns, leaves the supervisor running its loaded code and tells the
successor why; that the restarted process starts the successor from the
unconsumed handoff and restarts again at the next one; the restarted
process's argv, built from the settings for both argument lists the running
supervisors were started with; that main() keeps accepting every flag in that
argv; that the lock accepts a holder with this process's own ID; and a real
os.execv that keeps the process ID and lets the restarted program claim the lock.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-restarts-itself-on-main-code-test.py

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must keep this suite's git out of the
# repository the variable names. The repository root is three directories up.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

_handoff_supervisor_test_fixture_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor_test_fixture",
    Path(__file__).resolve().with_name("handoff-supervisor-test-fixture.py"))
fixture = importlib.util.module_from_spec(_handoff_supervisor_test_fixture_spec)
_handoff_supervisor_test_fixture_spec.loader.exec_module(fixture)

supervisor = fixture.supervisor
check = fixture.check
SCRIPT_PATH = fixture.SCRIPT_PATH
git_in = fixture.git_in
StubLaunchedSession = fixture.StubLaunchedSession
supervisor_names_replaced = fixture.supervisor_names_replaced

RESTART_FLAG = "--started-by-handoff-supervisor-restarting-itself-on-main-code"


class ProcessReplaced(BaseException):
    """Raised by the stand-in for os.execv: like a real exec, nothing after it runs."""


class StubIgnitionPlan:
    def compose(self, launch_time_git_sync_report, overview_refresh_due=(), memory_review_due=()):
        return "SUCCESSOR PROMPT"


def supervise_one_handoff(workspace: Path, case: str, own_checkout_sync_report: str,
                          exec_raises=None, handoff_extra: str = "", answer: str = "y",
                          restarts=True, exec_returns: bool = False):
    """Run the loop through one handoff with the restart's git sync and os.execv
    stubbed. The first session writes the handoff; a successor, if launched,
    exits cleanly so the loop stops."""
    handoff_directory = workspace / case
    handoff_directory.mkdir(parents=True)
    # None leaves the setting at its default.
    restart_setting = ({} if restarts is None
                       else {"restarts_itself_on_main_code_at_each_session_handoff": restarts})
    settings = supervisor.SupervisorSettings(
        agent=case, working_directory=workspace, handoff_directory=handoff_directory,
        agent_command="unused-stub-agent", first_prompt="first", **restart_setting)
    result = SimpleNamespace(events=[], prompts=[], exec_argv=None, replaced=False,
                             state_at_exec=None, console="")

    def launch(agent_command, session_id, working_directory, prompt, **_):
        result.events.append("launch")
        result.prompts.append(prompt)
        if len(result.prompts) == 1:
            settings.handoff_path.write_text(
                f"restart-counter: 1\nnext-step: carry on\n{handoff_extra}", encoding="utf-8")
            return StubLaunchedSession(-15, ended=False)
        return StubLaunchedSession(0)

    def sync(directory):
        if Path(directory) == supervisor.REPOSITORY_ROOT:
            result.events.append("sync own checkout")
            return own_checkout_sync_report
        return "launch-time-git-sync: stubbed"

    def replace(arguments):
        result.events.append("exec")
        result.exec_argv = list(arguments)
        result.state_at_exec = supervisor.read_supervisor_state(settings.state_path)
        if exec_raises is not None:
            raise exec_raises
        if exec_returns:
            return
        raise ProcessReplaced()

    def carry_over(settings_, retiring, fields, generation):
        result.events.append("carry over")
        return f"successor-{generation}", StubIgnitionPlan()

    console = io.StringIO()
    with supervisor_names_replaced(
            launch_agent_session=launch,
            stop_session=lambda process: (result.events.append("stop"), process.terminate()),
            remove_finished_worktrees_at_handoff=lambda directory: (
                result.events.append("cleanup") or "worktree cleanup: stubbed"),
            launch_time_git_sync=sync, replace_this_process_with=replace,
            carry_over_to_successor=carry_over, input=lambda prompt: answer,
            stdin_isatty=True), \
            contextlib.redirect_stdout(console), contextlib.redirect_stderr(io.StringIO()):
        try:
            supervisor.supervise_sessions(settings)
        except ProcessReplaced:
            result.replaced = True
    result.console = console.getvalue()
    result.settings = settings
    return result


def run_restart_placement_cases(workspace: Path):
    for case, report in (
            ("fastforwarded", "launch-time-git-sync: main fast-forwarded to main (abc1234)"),
            ("current", "launch-time-git-sync: main is current with main"),
            ("fastforwardedunreadtip", "launch-time-git-sync: main fast-forwarded to main (its new "
             "commit could not be read: x)\nnext step lines")):
        run = supervise_one_handoff(workspace, case, report)
        check(f"RESTART ({case}): after the stop and the worktree cleanup, before the carry-over, "
              "the process is replaced",
              run.replaced and run.events == ["launch", "stop", "cleanup", "sync own checkout", "exec"],
              str(run.events))
        check(f"RESTART ({case}): the handoff is still unconsumed when the process is replaced, "
              "so the restarted process starts the successor from it",
              run.state_at_exec is not None and run.state_at_exec.get("consumed_counter") is None,
              str(run.state_at_exec))
        check(f"RESTART ({case}): the console says it is restarting, before the exec",
              "restarting on main's code as process" in run.console, run.console[-400:])
    check("RESTART: the replacing argv is the one built from the settings",
          run.exec_argv == supervisor.handoff_supervisor_restart_arguments_build(run.settings),
          str(run.exec_argv))

    run = supervise_one_handoff(workspace, "neverrestarts",
                                "launch-time-git-sync: main fast-forwarded to main (abc1234)",
                                restarts=None)
    check("RESTART: settings not built by main() never restart, so a test importing the "
          "module keeps its own process",
          not run.replaced and "sync own checkout" not in run.events and len(run.prompts) == 2,
          str(run.events))
    check("RESTART: settings not built by main() do not say at startup that they were restarted",
          "restarted on main's code" not in run.console, run.console[-400:])


def run_dont_restart_case(workspace: Path):
    run = supervise_one_handoff(workspace, "dontrestart",
                                "launch-time-git-sync: main fast-forwarded to main (abc1234)",
                                handoff_extra="dont-restart: ask first\n", answer="y")
    check("DONT-RESTART: a dont-restart handoff answered y starts the successor in this "
          "process, with no git sync of its own checkout and no exec",
          not run.replaced and "sync own checkout" not in run.events
          and run.events == ["launch", "stop", "cleanup", "carry over", "launch"],
          str(run.events))


def run_restart_failure_cases(workspace: Path):
    for case, report, exec_raises, exec_returns, expected in (
            ("cannotfastforward",
             "launch-time-git-sync: main left as is — 2 uncommitted tracked change(s)",
             None, False, "launch-time-git-sync: main left as is — 2 uncommitted tracked change(s)"),
            ("behindandahead",
             "launch-time-git-sync: seat-branch is 3 ahead of main and 4 behind",
             None, False, "launch-time-git-sync: seat-branch is 3 ahead of main and 4 behind"),
            ("gitfailure",
             "launch-time-git-sync: main left as is — git failed\nRerun it; if it fails, stop.",
             None, False, "launch-time-git-sync: main left as is — git failed"),
            ("execraises", "launch-time-git-sync: main is current with main",
             PermissionError(13, "Permission denied"), False,
             "os.execv failed: PermissionError: [Errno 13] Permission denied"),
            ("execreturns", "launch-time-git-sync: main is current with main", None, True,
             "os.execv returned without replacing the process")):
        run = supervise_one_handoff(workspace, case, report, exec_raises=exec_raises,
                                    exec_returns=exec_returns)
        check(f"NOT RESTARTED ({case}): the supervisor carries on and starts the successor itself",
              not run.replaced and run.events[-2:] == ["carry over", "launch"]
              and len(run.prompts) == 2, str(run.events))
        successor_prompt = run.prompts[-1] if len(run.prompts) == 2 else ""
        check(f"NOT RESTARTED ({case}): the successor's initial agent instructions carry why, "
              "in one line",
              successor_prompt.startswith("SUCCESSOR PROMPT ")
              and f'reason: "{expected}". Tell the user that the handoff-supervisor did not '
                  "restart itself on main's code, and quote its reason" in successor_prompt
              and "only when the handoff-supervisor restarts" in successor_prompt
              and str(supervisor.REPOSITORY_ROOT) in successor_prompt,
              successor_prompt)
        check(f"NOT RESTARTED ({case}): the console says why",
              f"not restarted on main's code, carrying on with the code this process started "
              f"with: {expected}" in run.console, run.console[-600:])


def run_restarted_process_cases(workspace: Path):
    """The restarted process finds the handoff unconsumed and starts the
    successor without restarting at startup; at the next handoff it restarts."""
    handoff_directory = workspace / "restarted"
    handoff_directory.mkdir()
    settings = supervisor.SupervisorSettings(
        agent="restarted", working_directory=workspace, handoff_directory=handoff_directory,
        agent_command="unused-stub-agent", first_prompt="",
        restarts_itself_on_main_code_at_each_session_handoff=True,
        started_by_handoff_supervisor_restarting_itself_on_main_code=True)
    supervisor.write_supervisor_state(settings.state_path, {
        supervisor.LAUNCHED_SESSION_ID_STATE_KEY: "retiring-session", "generation": 3})
    settings.handoff_path.write_text("restart-counter: 1\nnext-step: carry on\n", encoding="utf-8")
    events, prompts, states_at_launch = [], [], []

    def launch(agent_command, session_id, working_directory, prompt, **_):
        events.append(("launch", session_id))
        prompts.append(prompt)
        states_at_launch.append(supervisor.read_supervisor_state(settings.state_path))
        # A process that failed to restart launches again; that session ends without a handoff, so the case ends.
        if len(prompts) > 1:
            return StubLaunchedSession(0)
        settings.handoff_path.write_text("restart-counter: 2\nnext-step: again\n", encoding="utf-8")
        return StubLaunchedSession(-15, ended=False)

    def sync(directory):
        if Path(directory) == supervisor.REPOSITORY_ROOT:
            events.append("sync own checkout")
            return "launch-time-git-sync: main is current with main"
        return "launch-time-git-sync: stubbed"

    def replace(arguments):
        events.append("exec")
        raise ProcessReplaced()

    console = io.StringIO()
    replaced = False
    with supervisor_names_replaced(
            launch_agent_session=launch, stop_session=lambda process: process.terminate(),
            remove_finished_worktrees_at_handoff=lambda directory: "worktree cleanup: stubbed",
            launch_time_git_sync=sync, replace_this_process_with=replace,
            carry_over_to_successor=lambda s, retiring, fields, generation: (
                events.append(("carry over", retiring, generation))
                or (f"successor-{generation}", StubIgnitionPlan())),
            stdin_isatty=True), \
            contextlib.redirect_stdout(console), contextlib.redirect_stderr(io.StringIO()):
        try:
            supervisor.supervise_sessions(settings)
        except ProcessReplaced:
            replaced = True
    check("RESTARTED PROCESS: it says at startup that the restart worked",
          f"restarted on main's code as process {os.getpid()}" in console.getvalue(),
          console.getvalue()[-400:])
    check("RESTARTED PROCESS: it starts the successor from the unconsumed handoff, carrying "
          "over the retiring session, without restarting at startup",
          events[:2] == [("carry over", "retiring-session", 4), ("launch", "successor-4")]
          and prompts[:1] == ["SUCCESSOR PROMPT"]
          and states_at_launch[:1] and states_at_launch[0].get("consumed_counter") == 1,
          f"{events} {states_at_launch[:1]}")
    check("RESTARTED PROCESS: at the next handoff it restarts again",
          replaced and events[2:] == ["sync own checkout", "exec"], str(events))


@contextlib.contextmanager
def a_claude_on_path(workspace: Path):
    directory = workspace / "claude-on-path"
    directory.mkdir(exist_ok=True)
    (directory / "claude").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (directory / "claude").chmod(0o755)
    saved = os.environ["PATH"]
    os.environ["PATH"] = f"{directory}{os.pathsep}{saved}"
    try:
        yield
    finally:
        os.environ["PATH"] = saved


def settings_main_builds(argv):
    captured = []
    with supervisor_names_replaced(supervise_sessions=lambda settings: captured.append(settings) or 0), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        exit_code = supervisor.main(argv)
    return exit_code, (captured[0] if captured else None)


def run_restart_arguments_cases(workspace: Path):
    home = Path.home()
    for agent in ("launcherstarted", "recoverystarted"):
        (home / "agents" / agent).mkdir(parents=True, exist_ok=True)
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    recovery_prompt = handoffs / "recoverystarted-resume-recovery-prompt.md"
    recovery_prompt.write_text("Resume.", encoding="utf-8")
    expected_tail = ["--agent-command", "claude", "--agent-update-timeout-seconds",
                     str(supervisor.AGENT_BINARY_UPDATE_TIMEOUT_SECONDS), RESTART_FLAG]
    with a_claude_on_path(workspace):
        # As scripts/launch-claude-ubuntu starts a supervisor, the --cd value unexpanded.
        exit_code, settings = settings_main_builds(
            ["--agent", "launcherstarted", "--cd", "~/agents/launcherstarted"])
        argv = supervisor.handoff_supervisor_restart_arguments_build(settings) if settings else []
        check("ARGV: a launcher's argument list restarts with the settings' values, the "
              "appended system prompt left to the restarted code's default",
              exit_code == 0 and argv == [
                  sys.executable, str(SCRIPT_PATH), "--agent", "launcherstarted",
                  "--cd", str((home / "agents" / "launcherstarted").resolve()),
                  "--handoff-dir", str(handoffs)] + expected_tail, str(argv))
        check("ARGV: main() marks the settings it builds as restarting, and not restarted",
              settings is not None and settings.restarts_itself_on_main_code_at_each_session_handoff
              and not settings.started_by_handoff_supervisor_restarting_itself_on_main_code,
              str(settings))

        # As scripts/recover-crashed-seats.py starts one.
        exit_code, settings = settings_main_builds(
            ["--agent", "recoverystarted", "--cd", str(home / "agents" / "recoverystarted"),
             "--handoff-dir", str(handoffs), "--resume-session-id", "6282ec41",
             "--first-prompt-file", str(recovery_prompt)])
        argv = supervisor.handoff_supervisor_restart_arguments_build(settings) if settings else []
        check("ARGV: a recovery's argument list restarts without --resume-session-id or "
              "--first-prompt-file, which describe its first start only",
              exit_code == 0 and argv == [
                  sys.executable, str(SCRIPT_PATH), "--agent", "recoverystarted",
                  "--cd", str((home / "agents" / "recoverystarted").resolve()),
                  "--handoff-dir", str(handoffs)] + expected_tail, str(argv))

        prompt_file = workspace / "own-appended-system-prompt.md"
        prompt_file.write_text("---\nagent text\n", encoding="utf-8")
        exit_code, settings = settings_main_builds(
            ["--agent", "recoverystarted", "--cd", str(workspace), "--handoff-dir", str(handoffs),
             "--agent-command", "claude", "--agent-update-timeout-seconds", "7",
             "--agent-append-system-prompt-file", str(prompt_file), RESTART_FLAG])
        argv = supervisor.handoff_supervisor_restart_arguments_build(settings) if settings else []
        check("ARGV: a given appended-system-prompt file and update timeout are passed on",
              argv[-6:] == ["claude", "--agent-update-timeout-seconds", "7",
                            "--agent-append-system-prompt-file", str(prompt_file), RESTART_FLAG],
              str(argv))
        # A path that sorts before the default one, so only an inequality test passes it on.
        settings_with_early_path = supervisor.SupervisorSettings(
            agent="earlypath", working_directory=workspace, handoff_directory=handoffs,
            agent_command="claude", first_prompt="",
            appended_system_prompt_file="/a/appended-system-prompt.md")
        early_argv = supervisor.handoff_supervisor_restart_arguments_build(settings_with_early_path)
        check("ARGV: any appended-system-prompt file other than the default is passed on",
              early_argv[-3:-1] == ["--agent-append-system-prompt-file",
                                    "/a/appended-system-prompt.md"], str(early_argv))
        # Given by its own flag, the default path is a string equal to, not the same object as, the default.
        settings_naming_the_default = supervisor.SupervisorSettings(
            agent="defaultnamed", working_directory=workspace, handoff_directory=handoffs,
            agent_command="claude", first_prompt="",
            appended_system_prompt_file="".join(str(supervisor.DEFAULT_APPENDED_SYSTEM_PROMPT_PATH)))
        default_named_argv = supervisor.handoff_supervisor_restart_arguments_build(
            settings_naming_the_default)
        check("ARGV: the default appended-system-prompt file, given as a flag, is not passed on",
              "--agent-append-system-prompt-file" not in default_named_argv, str(default_named_argv))
        check("ARGV: the restart flag is read into the settings, and passed on once",
              settings is not None
              and settings.started_by_handoff_supervisor_restarting_itself_on_main_code
              and argv.count(RESTART_FLAG) == 1, str(argv))


def run_restart_flag_names_stay_accepted_case(workspace: Path):
    """A running supervisor builds its restart argv with its own, older code, for
    the program on main; so main() must keep accepting every name in it."""
    prompt_file = workspace / "names-appended-system-prompt.md"
    prompt_file.write_text("---\nagent text\n", encoding="utf-8")
    argv = ["--agent", "flagnames", "--cd", str(workspace),
            "--handoff-dir", str(workspace / "flagnames"),
            "--agent-command", "claude", "--agent-update-timeout-seconds", "0",
            "--agent-append-system-prompt-file", str(prompt_file), RESTART_FLAG, "--check"]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exit_code = supervisor.main(argv)
    except SystemExit as stopped:
        exit_code = f"SystemExit({stopped.code})"
    check("FLAG NAMES: main() accepts --agent, --cd, --handoff-dir, --agent-command, "
          "--agent-update-timeout-seconds, --agent-append-system-prompt-file and the restart flag",
          exit_code in (0, 1), str(exit_code))


def run_own_process_id_in_lock_case(workspace: Path):
    """After os.execv the lock file holds the restarted process's own ID, and its
    command line runs handoff-supervisor.py --agent <seat>; the claim must take
    that as its own, not as an old-code supervisor still running."""
    lock_path = workspace / "ownpid-supervisor.lock"
    program = workspace / "own-pid-claim" / "handoff-supervisor.py"
    program.parent.mkdir()
    program.write_text(
        "import importlib.util, os, sys\n"
        "from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('supervisor', {str(SCRIPT_PATH)!r})\n"
        "supervisor = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(supervisor)\n"
        "lock_path = Path(sys.argv[1])\n"
        "lock_path.write_text(f'{os.getpid()}\\n')\n"
        "try:\n"
        "    supervisor.claim_supervisor_lock(lock_path)\n"
        "except Exception as error:\n"
        "    print(f'startup stopped: {error}')\n"
        "    sys.exit(4)\n"
        "print('claimed')\n",
        encoding="utf-8")
    finished = subprocess.run(
        [sys.executable, str(program), str(lock_path), "--agent", "ownpid"],
        capture_output=True, text=True, check=False, timeout=60)
    check("LOCK: a lock file holding this process's own ID, from a supervisor's command line, "
          "is claimed rather than refused as an old-code supervisor",
          finished.returncode == 0 and finished.stdout.strip() == "claimed",
          finished.stdout + finished.stderr)


def a_checkout_behind_origin_main(root: Path):
    remote = root / "remote.git"
    git_in(["init", "--quiet", "--bare", "--initial-branch=main", str(remote)], root)
    checkout = root / "supervisor-checkout"
    git_in(["clone", "--quiet", str(remote), str(checkout)], root)
    for directory in (checkout,):
        git_in(["config", "user.name", "fixture"], directory)
        git_in(["config", "user.email", "fixture@example.invalid"], directory)
    (checkout / "tracked.txt").write_text("one\n", encoding="utf-8")
    git_in(["add", "tracked.txt"], checkout)
    git_in(["commit", "--quiet", "-m", "one"], checkout)
    git_in(["push", "--quiet", "origin", "main"], checkout)
    other = root / "other-clone"
    git_in(["clone", "--quiet", str(remote), str(other)], root)
    git_in(["config", "user.name", "fixture"], other)
    git_in(["config", "user.email", "fixture@example.invalid"], other)
    (other / "tracked.txt").write_text("two\n", encoding="utf-8")
    git_in(["commit", "--quiet", "-am", "two"], other)
    git_in(["push", "--quiet", "origin", "main"], other)
    tip = git_in(["rev-parse", "HEAD"], other).stdout.strip()
    return checkout, tip


def run_real_exec_cases(workspace: Path):
    """A real os.execv, in a process of its own: the checkout is fast-forwarded,
    and the program that replaces the process has the same process ID."""
    root = workspace / "real-exec"
    root.mkdir()
    # Named as the supervisor, so a lock check that reads its command line takes it for one.
    stub = root / "replacing-program" / "handoff-supervisor.py"
    stub.parent.mkdir()
    stub.write_text(
        "import importlib.util, json, os, sys\n"
        "from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('supervisor', {str(SCRIPT_PATH)!r})\n"
        "supervisor = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(supervisor)\n"
        "try:\n"
        "    supervisor.claim_supervisor_lock(Path(os.environ['RESTART_TEST_LOCK_PATH']))\n"
        "    claim = 'claimed'\n"
        "except Exception as error:\n"
        "    claim = f'refused: {error}'\n"
        "print('REPLACED ' + json.dumps({'pid': os.getpid(), 'argv': sys.argv[1:], "
        "'claim': claim}))\n",
        encoding="utf-8")
    program = root / "restart-once.py"
    program.write_text(
        "import importlib.util, os, sys\n"
        "from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('supervisor', {str(SCRIPT_PATH)!r})\n"
        "supervisor = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(supervisor)\n"
        "supervisor.REPOSITORY_ROOT = Path(sys.argv[1])\n"
        "supervisor.HANDOFF_SUPERVISOR_SCRIPT_PATH = Path(sys.argv[2])\n"
        "print(f'PID {os.getpid()}')\n"
        "lock = supervisor.claim_supervisor_lock(Path(os.environ['RESTART_TEST_LOCK_PATH']))\n"
        "settings = supervisor.SupervisorSettings(\n"
        "    agent='realexec', working_directory=Path(sys.argv[1]),\n"
        "    handoff_directory=Path(sys.argv[1]), agent_command='claude', first_prompt='')\n"
        "print('NOT RESTARTED ' + supervisor."
        "handoff_supervisor_restart_itself_on_main_code_or_return_failure_report(settings))\n",
        encoding="utf-8")

    checkout, tip = a_checkout_behind_origin_main(root)
    environment = dict(os.environ, RESTART_TEST_LOCK_PATH=str(root / "realexec-supervisor.lock"))
    finished = subprocess.run([sys.executable, str(program), str(checkout), str(stub)],
                              capture_output=True, text=True, check=False, timeout=120,
                              env=environment)
    lines = finished.stdout.splitlines()
    process_id = next((line.split()[1] for line in lines if line.startswith("PID ")), None)
    replaced = next((json.loads(line[len("REPLACED "):]) for line in lines
                     if line.startswith("REPLACED ")), None)
    check("REAL EXEC: a checkout behind origin/main is fast-forwarded to it",
          git_in(["rev-parse", "HEAD"], checkout).stdout.strip() == tip, finished.stdout)
    check("REAL EXEC: the replacing program runs as the same process, with the restart argv",
          replaced is not None and str(replaced["pid"]) == process_id
          and replaced["argv"][:2] == ["--agent", "realexec"]
          and replaced["argv"][-1] == RESTART_FLAG
          and "--resume-session-id" not in replaced["argv"],
          finished.stdout + finished.stderr)
    check("REAL EXEC: the replacing program claims the lock the replaced process held, "
          "because the exec released the flock and the lock file names its own process ID",
          replaced is not None and replaced["claim"] == "claimed",
          finished.stdout + finished.stderr)
    check("REAL EXEC: what the process printed before the exec reaches its output",
          "restarting on main's code as process" in finished.stdout, finished.stdout)

    git_in(["reset", "--quiet", "--hard", "HEAD~1"], checkout)
    (checkout / "tracked.txt").write_text("edited\n", encoding="utf-8")
    finished = subprocess.run([sys.executable, str(program), str(checkout), str(stub)],
                              capture_output=True, text=True, check=False, timeout=120,
                              env=environment)
    check("REAL EXEC: a checkout with an uncommitted tracked change is left as is, and the "
          "process is not replaced but told why",
          "REPLACED " not in finished.stdout
          and "NOT RESTARTED launch-time-git-sync: main left as is — 1 uncommitted tracked change(s)"
          in finished.stdout, finished.stdout + finished.stderr)


with fixture.handoff_supervisor_suite_workspace() as workspace:
    run_restart_placement_cases(workspace)
    run_dont_restart_case(workspace)
    run_restart_failure_cases(workspace)
    run_restarted_process_cases(workspace)
    run_restart_arguments_cases(workspace)
    run_restart_flag_names_stay_accepted_case(workspace)
    run_own_process_id_in_lock_case(workspace)
    run_real_exec_cases(workspace)

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
