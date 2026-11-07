#!/usr/bin/env python3
"""Tests for handoff-supervisor.py: at each session-handoff the supervisor
fast-forwards its own checkout to origin/main and replaces its process with a
fresh start of itself from there, by os.execv.

Covered: where the restart sits in the cycle; that an ask-user-before-restart handoff is
not restarted on; that a checkout which cannot fast-forward, or an os.execv
that raises or returns, leaves the supervisor running its loaded code and tells the
successor why; that a reference-checkout which cannot fast-forward is put back on
main by the back-on-main program, run by the supervisor itself, after which the
supervisor restarts, passing on the leftovers branch, or, when the program fails,
does not restart and gives the successor the notice with the program's output, each
case driven through the supervisor's loop with the program stubbed; that the restarted
process tells its first successor, and only that one, the leftovers branch; that the restarted process starts the successor from the
unconsumed handoff and restarts again at the next one; that a retiring
session without a transcript, at a handoff the supervisor could not restart
on or in the restarted process, gives a successor started from the next
step and told the transcript is missing; the restarted
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
    def compose(self, launch_time_git_sync_report, overview_refresh_due=(), memory_review_due=(),
                branch_state_instruction=""):
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
                f"session-handoff-sequence-number: 1\nnext-step: carry on\n{handoff_extra}", encoding="utf-8")
            return StubLaunchedSession(-15, ended=False)
        return StubLaunchedSession(0)

    def sync(directory):
        if Path(directory) == supervisor.REPOSITORY_ROOT:
            result.events.append("sync own checkout")
            # An iterator gives one report per sync of the own checkout.
            return (own_checkout_sync_report if isinstance(own_checkout_sync_report, str)
                    else next(own_checkout_sync_report))
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


def run_ask_user_before_restart_case(workspace: Path):
    run = supervise_one_handoff(workspace, "dontrestart",
                                "launch-time-git-sync: main fast-forwarded to main (abc1234)",
                                handoff_extra="ask-user-before-restart: ask first\n", answer="y")
    check("ASK-USER-BEFORE-RESTART: an ask-user-before-restart handoff answered y starts the successor in this "
          "process, with no git sync of its own checkout and no exec",
          not run.replaced and "sync own checkout" not in run.events
          and run.events == ["launch", "stop", "cleanup", "carry over", "launch"],
          str(run.events))


HANDOFF_PROGRAMS = "~/Projects/nedschorus/nc-systems/handoff/"
BACK_ON_MAIN_COMMAND = (f"python3 {HANDOFF_PROGRAMS}handoff-reference-checkout-back-on-main-after-"
                        "pushing-leftovers-to-a-branch.py")


def back_on_main_program_failed_ending(command: str, output: str) -> str:
    return ("That checkout would not fast-forward to main, so the handoff-supervisor ran the "
            "program that saves the checkout's leftovers to a pushed branch and puts it back on "
            f"main, and that program failed, printing: \"{output}\". Work out the cause from what "
            f"it printed, fix the cause, and run the program again as {command}, the form that "
            "works from this agent-session; when the cause is not one you can fix, tell the user "
            "what the program printed. The handoff-supervisor does not run the program again once "
            "the checkout is on main, which it can be even after a failed push, so a leftovers "
            "branch the program could not push stays only in that checkout until you run the "
            "program again. Once the checkout is on main, the handoff-supervisor restarts itself "
            "at the next session-handoff at which it starts the successor without stopping to ask "
            "the user.")


def leftovers_pushed_notice(branches: str, reference_checkout=None) -> str:
    reference_checkout = reference_checkout or supervisor.REFERENCE_CHECKOUT
    return (f"At this session-handoff the reference-checkout {reference_checkout} would "
            "not fast-forward to main, so the handoff-supervisor saved what was left over in it "
            f"to the git branch {branches}, pushed to origin, and put the checkout back on main. "
            f"Name {branches} "
            "to the user: what it holds was left in that checkout, where no agent works, and may "
            "be someone's lost work.")


def run_not_restarted_notice_names_the_tool_cases(workspace: Path):
    """The notice names the program that puts the reference-checkout back on main, with what
    it printed, when the handoff-supervisor ran it and it failed, and the restart program for
    any other cause; each command as this machine runs it."""
    restart = (f"python3 {HANDOFF_PROGRAMS}handoff-supervisor-restart-onto-main-code-by-relaunch-"
               "from-reference-checkout.py seatname")
    commands = {
        "restart on the Mac": f"`{restart}`",
        "restart on ned-box": f"`ssh nedlern@ned-box '{restart}'`",
        "back on main on the Mac": f"`{BACK_ON_MAIN_COMMAND}`",
        "back on main on ned-box": f"`ssh nedlern@ned-box '{BACK_ON_MAIN_COMMAND}'`"}
    cannot_fast_forward = "launch-time-git-sync: main left as is — 2 uncommitted tracked change(s)"
    program_output = "handoff-reference-checkout-back-on-main-...: a step failed: git push refused"
    for case, report, output, on_the_mac, expected in (
            ("back-on-main program failed on ned-box", cannot_fast_forward, program_output,
             False, "back on main on ned-box"),
            ("back-on-main program failed on the Mac", cannot_fast_forward, program_output,
             True, "back on main on the Mac"),
            ("os.execv failed on ned-box",
             "os.execv failed: PermissionError: [Errno 13] Permission denied", "", False,
             "restart on ned-box"),
            ("os.execv returned on the Mac",
             "os.execv returned without replacing the process", "", True, "restart on the Mac"),
            ("another checkout will not fast-forward on the Mac", cannot_fast_forward, "", True,
             "restart on the Mac")):
        notice = supervisor.handoff_supervisor_not_restarted_on_main_code_notice(
            report, "seatname", back_on_main_program_failure_output=output, on_the_mac=on_the_mac)
        ending = (
            back_on_main_program_failed_ending(commands[expected], output)
            if expected.startswith("back on main") else
            "The restart program restarts it from the reference-checkout "
            f"{supervisor.REFERENCE_CHECKOUT}. Once you have done what that program's docstring "
            f"says the agent-seat does before running it, run {commands[expected]}, and then do "
            "what the docstring says the agent-seat does after.")
        check(f"NOTICE TOOL ({case}): the notice names {commands[expected]} and no other command",
              f'reason: "{report}". Tell the user now' in notice
              and f"name the checkout {supervisor.REPOSITORY_ROOT}. " in notice
              and notice.endswith(ending)
              and all((command in notice) == (name == expected)
                      for name, command in commands.items()),
              notice)


def supervise_one_handoff_from_the_reference_checkout(workspace: Path, case: str,
                                                      back_on_main, exec_raises=None):
    """supervise_one_handoff with the supervisor's own checkout taken for the
    reference-checkout, which first will not fast-forward and, once the stubbed back-on-main
    program has run, is current with main."""
    program = supervisor.reference_checkout_back_on_main
    calls = []

    def put_back_on_main(checkout, today):
        calls.append(checkout)
        return back_on_main(checkout)

    stub_program = SimpleNamespace(
        put_reference_checkout_back_on_main=put_back_on_main, StepFailed=program.StepFailed,
        reference_checkout_back_on_main_failure_text_build=(
            program.reference_checkout_back_on_main_failure_text_build),
        reference_checkout_back_on_main_success_line_build=(
            program.reference_checkout_back_on_main_success_line_build))
    reports = iter(["launch-time-git-sync: main left as is — 2 uncommitted tracked change(s)",
                    "launch-time-git-sync: main is current with main"])
    with supervisor_names_replaced(REFERENCE_CHECKOUT=supervisor.REPOSITORY_ROOT,
                                   reference_checkout_back_on_main=stub_program):
        run = supervise_one_handoff(workspace, case, reports, exec_raises=exec_raises)
    run.back_on_main_calls = calls
    return run


def run_reference_checkout_back_on_main_program_cases(workspace: Path):
    cannot_fast_forward = "launch-time-git-sync: main left as is — 2 uncommitted tracked change(s)"
    program = supervisor.reference_checkout_back_on_main

    def fails(checkout):
        raise program.StepFailed("git push refused by the test")

    run = supervise_one_handoff_from_the_reference_checkout(workspace, "backonmainfails", fails)
    output = program.reference_checkout_back_on_main_failure_text_build(
        supervisor.REPOSITORY_ROOT, program.StepFailed("git push refused by the test"))
    on_the_mac = sys.platform == "darwin"
    command = (f"`{BACK_ON_MAIN_COMMAND}`" if on_the_mac
               else f"`ssh nedlern@ned-box '{BACK_ON_MAIN_COMMAND}'`")
    successor_prompt = run.prompts[-1] if len(run.prompts) == 2 else ""
    check("BACK ON MAIN FAILS: the supervisor runs the program once on the reference-checkout, "
          "does not restart, and starts the successor itself",
          run.back_on_main_calls == [supervisor.REPOSITORY_ROOT] and not run.replaced
          and "exec" not in run.events and run.events[-2:] == ["carry over", "launch"],
          f"{run.events} {run.back_on_main_calls}")
    check("BACK ON MAIN FAILS: the successor's initial-agent-instructions end with the notice "
          "that quotes the sync's reason and the program's output, and names the program's "
          "command for this machine",
          successor_prompt.startswith("SUCCESSOR PROMPT ")
          and f'reason: "{cannot_fast_forward}". Tell the user now' in successor_prompt
          and successor_prompt.endswith(back_on_main_program_failed_ending(command, output)),
          successor_prompt)
    check("BACK ON MAIN FAILS: the console carries the program's output and says why it did "
          "not restart",
          output in run.console and "not restarted on main's code, carrying on with the code "
          f"this process started with: {cannot_fast_forward}" in run.console, run.console[-900:])

    branch = "reference-checkout-leftovers-2026-11-05"
    run = supervise_one_handoff_from_the_reference_checkout(
        workspace, "backonmainpushes", lambda checkout: ("abc1234", [branch]))
    flag = "--reference-checkout-leftovers-branch-pushed-before-this-restart"
    check("BACK ON MAIN SUCCEEDS: the supervisor restarts, passing the leftovers branch to the "
          "restarted process before the restart flag",
          run.replaced and run.events == ["launch", "stop", "cleanup", "sync own checkout",
                                          "sync own checkout", "exec"]
          and run.exec_argv is not None and run.exec_argv[-3:] == [flag, branch, RESTART_FLAG],
          f"{run.events} {run.exec_argv}")
    check("BACK ON MAIN SUCCEEDS: the console carries the program's success line",
          f"is on main at origin/main abc1234; its leftovers are saved on {branch}" in run.console,
          run.console[-900:])

    run = supervise_one_handoff_from_the_reference_checkout(
        workspace, "backonmainpushesexecfails", lambda checkout: ("abc1234", [branch]),
        exec_raises=PermissionError(13, "Permission denied"))
    successor_prompt = run.prompts[-1] if len(run.prompts) == 2 else ""
    check("BACK ON MAIN SUCCEEDS, EXEC FAILS: the successor is told why it did not restart, "
          "and the leftovers branch",
          not run.replaced and 'reason: "os.execv failed: PermissionError: [Errno 13] '
          'Permission denied"' in successor_prompt
          # Inside the run the reference-checkout was the supervisor's own checkout.
          and successor_prompt.endswith(
              " " + leftovers_pushed_notice(branch, supervisor.REPOSITORY_ROOT)), successor_prompt)


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
              and f'reason: "{expected}". Tell the user now that the handoff-supervisor did not '
                  "restart itself on main's code, quote its reason, and name the checkout "
                  f"{supervisor.REPOSITORY_ROOT}." in successor_prompt
              and "only when the handoff-supervisor restarts" in successor_prompt,
              successor_prompt)
        restart_command = (
            f"python3 {HANDOFF_PROGRAMS}handoff-supervisor-restart-onto-main-code-by-relaunch-"
            f"from-reference-checkout.py {case}")
        if sys.platform != "darwin":
            restart_command = f"ssh nedlern@ned-box '{restart_command}'"
        check(f"NOT RESTARTED ({case}): the successor's initial agent instructions end with the "
              "notice's restart-program ending, since its checkout is not the reference-checkout",
              successor_prompt.endswith(
                  "The restart program restarts it from the reference-checkout "
                  f"{supervisor.REFERENCE_CHECKOUT}. Once you have done what that program's "
                  "docstring says the agent-seat does before running it, run "
                  f"`{restart_command}`, and then do what the docstring says the agent-seat "
                  "does after."), successor_prompt)
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
    settings.handoff_path.write_text("session-handoff-sequence-number: 1\nnext-step: carry on\n", encoding="utf-8")
    events, prompts, states_at_launch = [], [], []

    def launch(agent_command, session_id, working_directory, prompt, **_):
        events.append(("launch", session_id))
        prompts.append(prompt)
        states_at_launch.append(supervisor.read_supervisor_state(settings.state_path))
        # A process that failed to restart launches again; that session ends without a handoff, so the case ends.
        if len(prompts) > 1:
            return StubLaunchedSession(0)
        settings.handoff_path.write_text("session-handoff-sequence-number: 2\nnext-step: again\n", encoding="utf-8")
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


def run_restarted_process_told_leftovers_branch_case(workspace: Path):
    handoff_directory = workspace / "restartedleftovers"
    handoff_directory.mkdir()
    branch = "reference-checkout-leftovers-2026-11-05-2"
    settings = supervisor.SupervisorSettings(
        agent="restartedleftovers", working_directory=workspace,
        handoff_directory=handoff_directory, agent_command="unused-stub-agent", first_prompt="",
        restarts_itself_on_main_code_at_each_session_handoff=True,
        started_by_handoff_supervisor_restarting_itself_on_main_code=True,
        reference_checkout_leftovers_branches_pushed_before_this_restart=(branch,))
    supervisor.write_supervisor_state(settings.state_path, {
        supervisor.LAUNCHED_SESSION_ID_STATE_KEY: "retiring-session", "generation": 3})
    settings.handoff_path.write_text("session-handoff-sequence-number: 1\nnext-step: carry on\n",
                                     encoding="utf-8")
    prompts, exec_argv = [], []

    def launch(agent_command, session_id, working_directory, prompt, **_):
        prompts.append(prompt)
        settings.handoff_path.write_text("session-handoff-sequence-number: 2\nnext-step: again\n",
                                         encoding="utf-8")
        return StubLaunchedSession(-15, ended=False)

    def replace(arguments):
        exec_argv.extend(arguments)
        raise ProcessReplaced()

    with supervisor_names_replaced(
            launch_agent_session=launch, stop_session=lambda process: process.terminate(),
            remove_finished_worktrees_at_handoff=lambda directory: "worktree cleanup: stubbed",
            launch_time_git_sync=lambda directory: "launch-time-git-sync: main is current with main",
            replace_this_process_with=replace,
            carry_over_to_successor=lambda s, retiring, fields, generation: (
                f"successor-{generation}", StubIgnitionPlan()),
            stdin_isatty=True), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            supervisor.supervise_sessions(settings)
        except ProcessReplaced:
            pass
    check("RESTARTED PROCESS, LEFTOVERS: its first successor is told the leftovers branch",
          prompts == ["SUCCESSOR PROMPT " + leftovers_pushed_notice(branch)], str(prompts))
    check("RESTARTED PROCESS, LEFTOVERS: its own restart at the next handoff does not pass the "
          "branch on again",
          exec_argv and "--reference-checkout-leftovers-branch-pushed-before-this-restart"
          not in exec_argv, str(exec_argv))


def recovery_note_for_a_missing_transcript(occasion: str, session_id: str, workspace: Path) -> str:
    transcript = supervisor.project_directory_for_working_directory(workspace) / f"{session_id}.jsonl"
    return (f"(Recovered at {occasion}: the previous session's conversation-tail is unavailable, "
            "because the handoff-supervisor could not extract session "
            f"{session_id}'s session-dialog, and that session's transcript is not at "
            f"{transcript} or in any other folder under {supervisor.PROJECTS_ROOT}/; this "
            "next-step and the repository are your whole context.) ")


def run_missing_transcript_cases(workspace: Path):
    """The retiring session has no transcript, so the real extractor fails. A
    supervisor that could not restart starts the successor from the next step;
    a restarted process does the same at startup, and says it was a handoff."""
    case = "missingtranscriptnotrestarted"
    handoff_directory = workspace / case
    handoff_directory.mkdir()
    settings = supervisor.SupervisorSettings(
        agent=case, working_directory=workspace, handoff_directory=handoff_directory,
        agent_command="unused-stub-agent", first_prompt="first",
        restarts_itself_on_main_code_at_each_session_handoff=True)
    launched_session_ids, prompts = [], []
    cannot_fast_forward = "launch-time-git-sync: main left as is — 2 uncommitted tracked change(s)"

    def launch(agent_command, session_id, working_directory, prompt, **_):
        launched_session_ids.append(session_id)
        prompts.append(prompt)
        if len(prompts) == 1:
            settings.handoff_path.write_text("session-handoff-sequence-number: 1\nnext-step: carry on\n",
                                             encoding="utf-8")
            return StubLaunchedSession(-15, ended=False)
        return StubLaunchedSession(0)

    console, errors = io.StringIO(), io.StringIO()
    with supervisor_names_replaced(
            launch_agent_session=launch, stop_session=lambda process: process.terminate(),
            remove_finished_worktrees_at_handoff=lambda directory: "worktree cleanup: stubbed",
            launch_time_git_sync=lambda directory: (
                cannot_fast_forward if Path(directory) == supervisor.REPOSITORY_ROOT
                else "launch-time-git-sync: stubbed"),
            replace_this_process_with=lambda arguments: (_ for _ in ()).throw(ProcessReplaced()),
            memory_review_due_lines=lambda: (),
            stdin_isatty=True), \
            contextlib.redirect_stdout(console), contextlib.redirect_stderr(errors):
        exit_code = supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    retiring = launched_session_ids[0] if launched_session_ids else ""
    successor_prompt = prompts[1] if len(prompts) == 2 else ""
    check("MISSING TRANSCRIPT, NOT RESTARTED: the extractor fails, and the supervisor still "
          "starts the successor and consumes the handoff",
          exit_code == 0 and len(prompts) == 2 and state.get("consumed_counter") == 1
          and "not relaunching" not in console.getvalue() + errors.getvalue(),
          f"{exit_code!r} {len(prompts)} {state} {errors.getvalue()[-400:]}")
    check("MISSING TRANSCRIPT, NOT RESTARTED: the successor's prompt says the transcript is "
          "missing and why the supervisor did not restart, then gives the next step",
          successor_prompt.startswith(
              recovery_note_for_a_missing_transcript("a handoff", retiring, workspace))
          # The not-restarted line follows the next step, as it does in a prompt from a dialog.
          and supervisor.NEXT_STEP_HEADING + "carry on " in successor_prompt
          and f'reason: "{cannot_fast_forward}"' in successor_prompt,
          successor_prompt[:900])

    for case, restarted, occasion in (("missingtranscriptrestarted", True, "a handoff"),
                                      ("missingtranscriptboot", False, "supervisor boot")):
        handoff_directory = workspace / case
        handoff_directory.mkdir()
        settings = supervisor.SupervisorSettings(
            agent=case, working_directory=workspace, handoff_directory=handoff_directory,
            agent_command="unused-stub-agent", first_prompt="",
            restarts_itself_on_main_code_at_each_session_handoff=True,
            started_by_handoff_supervisor_restarting_itself_on_main_code=restarted)
        retiring = f"0badbeef-0000-4000-8000-{os.getpid():012d}"
        supervisor.write_supervisor_state(settings.state_path, {
            supervisor.LAUNCHED_SESSION_ID_STATE_KEY: retiring, "generation": 3})
        settings.handoff_path.write_text("session-handoff-sequence-number: 1\nnext-step: carry on\n",
                                         encoding="utf-8")
        prompts = []

        def launch_once(agent_command, session_id, working_directory, prompt, **_):
            prompts.append(prompt)
            return StubLaunchedSession(0)

        with supervisor_names_replaced(
                launch_agent_session=launch_once,
                launch_time_git_sync=lambda directory: "launch-time-git-sync: stubbed",
                memory_review_due_lines=lambda: (),
                stdin_isatty=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            supervisor.supervise_sessions(settings)
        state = supervisor.read_supervisor_state(settings.state_path)
        check(f"MISSING TRANSCRIPT ({case}): the successor starts from the next step, its prompt "
              f"says it was recovered at {occasion} and that the transcript is missing",
              len(prompts) == 1 and state.get("consumed_counter") == 1
              and prompts[0].startswith(
                  recovery_note_for_a_missing_transcript(occasion, retiring, workspace))
              and prompts[0].endswith(supervisor.NEXT_STEP_HEADING + "carry on"),
              f"{state} {prompts[:1]!r}"[:900])


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
            appended_system_prompt_file_as_given_by_flag="/a/appended-system-prompt.md")
        early_argv = supervisor.handoff_supervisor_restart_arguments_build(settings_with_early_path)
        check("ARGV: any appended-system-prompt file other than the default is passed on",
              early_argv[-3:-1] == ["--agent-append-system-prompt-file",
                                    "/a/appended-system-prompt.md"], str(early_argv))
        # Given by its own flag, the default path is a string equal to, not the same object as, the default.
        settings_naming_the_default = supervisor.SupervisorSettings(
            agent="defaultnamed", working_directory=workspace, handoff_directory=handoffs,
            agent_command="claude", first_prompt="",
            appended_system_prompt_file_as_given_by_flag="".join(
                str(supervisor.DEFAULT_APPENDED_SYSTEM_PROMPT_PATH)))
        default_named_argv = supervisor.handoff_supervisor_restart_arguments_build(
            settings_naming_the_default)
        check("ARGV: the default appended-system-prompt file, given as a flag, is not passed on",
              "--agent-append-system-prompt-file" not in default_named_argv, str(default_named_argv))

        exit_code, settings_without_prompt = settings_main_builds(
            ["--agent", "noprompt", "--cd", str(workspace), "--handoff-dir", str(handoffs),
             "--agent-append-system-prompt-file", ""])
        no_prompt_argv = (supervisor.handoff_supervisor_restart_arguments_build(
            settings_without_prompt) if settings_without_prompt else [])
        check("ARGV: an empty --agent-append-system-prompt-file, which asks for no appended "
              "system prompt, is passed on so the restart does not turn the default back on",
              exit_code == 0
              and no_prompt_argv[-3:-1] == ["--agent-append-system-prompt-file", ""],
              str(no_prompt_argv))
        missing_prompt_file = str(workspace / "missing-appended-system-prompt.md")
        exit_code, settings_with_missing_prompt = settings_main_builds(
            ["--agent", "missingprompt", "--cd", str(workspace), "--handoff-dir", str(handoffs),
             "--agent-append-system-prompt-file", missing_prompt_file])
        missing_prompt_argv = (supervisor.handoff_supervisor_restart_arguments_build(
            settings_with_missing_prompt) if settings_with_missing_prompt else [])
        check("ARGV: a given appended-system-prompt file missing at startup is passed on, "
              "not replaced by the default",
              exit_code == 0 and settings_with_missing_prompt.appended_system_prompt_file == ""
              and missing_prompt_argv[-3:-1] == ["--agent-append-system-prompt-file",
                                                 missing_prompt_file],
              str(missing_prompt_argv))
        exit_code, settings_with_leftovers = settings_main_builds(
            ["--agent", "recoverystarted", "--cd", str(workspace), "--handoff-dir", str(handoffs),
             "--reference-checkout-leftovers-branch-pushed-before-this-restart", "one",
             "--reference-checkout-leftovers-branch-pushed-before-this-restart", "two",
             RESTART_FLAG])
        check("ARGV: each leftovers branch flag is read into the settings, in order",
              exit_code == 0 and settings_with_leftovers is not None
              and settings_with_leftovers.reference_checkout_leftovers_branches_pushed_before_this_restart
              == ("one", "two"), str(settings_with_leftovers))
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
            "--agent-append-system-prompt-file", str(prompt_file),
            "--reference-checkout-leftovers-branch-pushed-before-this-restart",
            "reference-checkout-leftovers-2026-11-05", RESTART_FLAG, "--check"]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exit_code = supervisor.main(argv)
    except SystemExit as stopped:
        exit_code = f"SystemExit({stopped.code})"
    check("FLAG NAMES: main() accepts --agent, --cd, --handoff-dir, --agent-command, "
          "--agent-update-timeout-seconds, --agent-append-system-prompt-file, "
          "--reference-checkout-leftovers-branch-pushed-before-this-restart and the restart flag",
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
        "handoff_supervisor_restart_itself_on_main_code_after_putting_reference_checkout_back_on_main_or_return_successor_notice(settings))\n",
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
          and "NOT RESTARTED The handoff-supervisor of this agent-seat did not restart"
          in finished.stdout
          and 'reason: "launch-time-git-sync: main left as is — 1 uncommitted tracked change(s)"'
          in finished.stdout, finished.stdout + finished.stderr)


with fixture.handoff_supervisor_suite_workspace() as workspace:
    run_restart_placement_cases(workspace)
    run_ask_user_before_restart_case(workspace)
    run_restart_failure_cases(workspace)
    run_not_restarted_notice_names_the_tool_cases(workspace)
    run_reference_checkout_back_on_main_program_cases(workspace)
    run_restarted_process_cases(workspace)
    run_restarted_process_told_leftovers_branch_case(workspace)
    run_missing_transcript_cases(workspace)
    run_restart_arguments_cases(workspace)
    run_restart_flag_names_stay_accepted_case(workspace)
    run_own_process_id_in_lock_case(workspace)
    run_real_exec_cases(workspace)

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
