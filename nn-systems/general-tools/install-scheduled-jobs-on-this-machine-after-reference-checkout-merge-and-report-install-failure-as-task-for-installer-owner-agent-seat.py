#!/usr/bin/env python3
"""Run install-scheduled-jobs-on-this-machine.py --install, then --remove-not-in-table, after a merge into a machine's reference-checkout.

Usage (git runs it from scripts/git-client-side-hooks/post-merge, in the
checkout's top directory, after every merge, a fast-forward included):
  nn-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py [--print-outcome]

The hook gives no option and the program prints only FAILED messages. An agent
or the user who reruns it by hand, as its messages say to, gives
--print-outcome, and the program then also prints one line saying how the run
ended: not a reference-checkout, both steps exited 0 with the tasks marked
completed, or the step that failed again with the task that now holds it.

Every checkout of the clone runs the same post-merge hook, because
core.hooksPath names the reference-checkout's hook directory. In any checkout
but one of REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME this program does nothing.
In a reference-checkout, it runs the installer beside this file with each
option of INSTALLER_STEPS in turn: --install, so a job added to or changed in
the table, scheduled-jobs-on-each-machine.json, or an install that failed
before, is put right at the next pull; then, only when --install exited 0,
--remove-not-in-table, so a job the merge dropped from the table is taken off
the machine. A step fails when it exits nonzero, and the first step that fails
is the failed step. The installer's output is not passed on when both steps
succeed.

On ned-box, the program keeps a failed step as a task on the task list of
OWNING_AGENT_SEAT, the agent-seat that owns the installer, under the subject
SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST.
An open task is one of that subject not marked completed.

When a step fails, each open task gets as its description the failed step's
option, exit code and output, or, when none is open, a new task is written
with agent-seat-task-list-new-pending-task-write-common.py; nothing is
printed. Every open task is rewritten, not one of them, so none is left
telling its reader an older failure. When a write fails, the tasks rewritten
before it hold the new description and the rest keep the old one, and the
program prints a FAILED message, as the paragraph after next says.

When both steps exit 0, each open task is marked completed, and nothing is
printed. When marking one completed fails, it and the open tasks after it
stay open, the hook's run does not report it, and the exit is still 0: an
open task tells its reader to rerun this program with --print-outcome, which
reports the failed marking, and the next pull at which both succeed marks
them completed.

When the task cannot be written, or a step failed on the Mac, where
OWNING_AGENT_SEAT's task list is not, a FAILED message holding the failed
step's output goes to standard error instead: git puts it on its own stderr,
and scripts/checkout-freshness-catch-up.py, which fast-forwards the
reference-checkout, shows the user any FAILED line there.

Git ignores a post-merge hook's exit code; the merge stands either way.

Exit codes: 0 not a reference-checkout, both steps succeeded, or the failed
step was written as a task; 1 a step failed and writing it as a task failed,
or, on the Mac, was not tried, with the FAILED message on standard error.

Each *_TEST_OVERRIDE_ENVIRONMENT_VARIABLE constant names an environment
variable whose value, when set, replaces a path, for
nn-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat-test.py,
which runs no real install:
  - SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE: the
    installer to run, in place of install-scheduled-jobs-on-this-machine.py
    beside this file;
  - NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE:
    ned-box's reference-checkout, in place of ned-box's entry in
    REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME; the Mac's entry has no override;
  - AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE: the
    directory that holds every agent-seat's task list, in place of
    ~/.claude/tasks; OWNING_AGENT_SEAT's list is the directory
    nedsnodes-<OWNING_AGENT_SEAT>-tasks in it.
"""

# Messages here follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parent
PROGRAM = "nn-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py"
SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY = (
    "nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py")
OWNING_AGENT_SEAT = "reboot-test"
NED_BOX = "ned-box"
MAC = "the Mac"
EXIT_DONE = 0
EXIT_FAILED = 1

SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE = (
    "NEDSNODES_SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE")
NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE = (
    "NEDSNODES_NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE")
AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE = (
    "NEDSNODES_AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE")


def _load(module_name, file_name):
    specification = importlib.util.spec_from_file_location(module_name, GENERAL_TOOLS / file_name)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ned_box_paths = _load("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                      "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
mac_reference_checkout = _load(
    "mac_reference_checkout_launcher_scripts_directory_path_constant_common",
    "mac-reference-checkout-launcher-scripts-directory-path-constant-common.py")
agent_seat_task_list = _load("agent_seat_task_list_new_pending_task_write_common",
                             "agent-seat-task-list-new-pending-task-write-common.py")
agent_seat_task_file = _load("agent_seat_task_list_task_file_rewrite_common",
                             "agent-seat-task-list-task-file-rewrite-common.py")

REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME = {
    NED_BOX: f"{ned_box_paths.NED_BOX_HOME}/Projects/nedsnodes",
    MAC: str(Path(mac_reference_checkout.MAC_REFERENCE_CHECKOUT_LAUNCHER_SCRIPTS_DIRECTORY_PATH).parent),
}
SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST = (
    "Scheduled jobs: nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py "
    "--install or --remove-not-in-table failed after a pull into ned-box's reference-checkout")
INSTALL = "--install"
REMOVE_NOT_IN_TABLE = "--remove-not-in-table"
INSTALLER_STEPS = (INSTALL, REMOVE_NOT_IN_TABLE)
SCHEDULED_JOBS_TABLE = "nn-systems/general-tools/scheduled-jobs-on-each-machine.json"
BOTH_INSTALLER_STEPS = f"both installer steps, `{INSTALL}` and then `{REMOVE_NOT_IN_TABLE}`,"
PRINT_OUTCOME_COMMAND_LINE_FLAG = "--print-outcome"
WHAT_A_FAILED_STEP_MAY_LEAVE_ON_THE_MACHINE = {
    INSTALL: f"may not run every job that {SCHEDULED_JOBS_TABLE} gives it",
    REMOVE_NOT_IN_TABLE: f"may still run a job that {SCHEDULED_JOBS_TABLE} does not give it",
}


def step_command_text(reference_checkout, step):
    return (f"python3 {reference_checkout}/"
            f"{SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY} {step}")


def rerun_command_text(reference_checkout):
    return f"cd {reference_checkout} && python3 {PROGRAM} {PRINT_OUTCOME_COMMAND_LINE_FLAG}"


def failed_step_sentence(machine, reference_checkout, step, exit_code):
    after_install = (f", which it runs only after `{INSTALL}` exits 0,"
                     if step == REMOVE_NOT_IN_TABLE else "")
    return (f"after the latest merge into {machine}'s reference-checkout, {reference_checkout}, "
            f"its post-merge hook ran `{step_command_text(reference_checkout, step)}`"
            f"{after_install} and the {step} step failed: it exited {exit_code}, so {machine} "
            f"{WHAT_A_FAILED_STEP_MAY_LEAVE_ON_THE_MACHINE[step]}.")


def kept_line_instruction(machine, condition, step):
    """The instruction line for a KEPT line, which only --remove-not-in-table prints."""
    if step != REMOVE_NOT_IN_TABLE:
        return ""
    return (f"{condition}, that crontab line runs a job the table does not give {machine} "
            f"together with a job that is not a program of the clone, and every pull fails this "
            f"way until the line is edited: ask the user to edit that line by hand in "
            f"{machine}'s crontab, keeping the job that is not the clone's.\n")


def find_and_fix_cause_instruction(condition, machine):
    return (f"{condition}, find the cause from the installer's lines at the end of this text and "
            f"fix it: in a pull request when the cause is in the installer or the table, or on "
            f"{machine} when it is in {machine}'s own state, such as its crontab.\n")


def rerun_instruction(condition, machine, reference_checkout):
    rerun = rerun_command_text(reference_checkout)
    what_it_does = (f"it runs {BOTH_INSTALLER_STEPS} again and prints how they ended")
    if machine == NED_BOX:
        return f"{condition}, then run `{rerun}` on ned-box: {what_it_does}.\n"
    return (f"{condition}, then ask the user to run `{rerun}` in a Terminal on {machine}, which "
            f"ned-box cannot run commands on, and to paste what it prints into your session: "
            f"{what_it_does}.\n")


def user_only_fix_instruction(condition):
    return (f"{condition}the fix needs something only the user can do, tell the user what "
            f"failed, quoting the installer's lines, and what to do.\n")


def failed_step_task_description(reference_checkout, step, exit_code, output):
    sentence = failed_step_sentence(NED_BOX, reference_checkout, step, exit_code)
    rerun = rerun_command_text(reference_checkout)
    return (
        f"{sentence[0].upper()}{sentence[1:]}\n"
        + find_and_fix_cause_instruction("Before anything else", NED_BOX)
        + kept_line_instruction(NED_BOX, "When the installer printed a KEPT line", step)
        + f"Then run `{rerun}` on ned-box: it runs {BOTH_INSTALLER_STEPS} again, marks this "
        f"task completed when both exit 0 or rewrites this description with the new failure, "
        f"and prints which it did.\n"
        + user_only_fix_instruction("When ")
        + f"The post-merge hook does the same at every pull into the reference-checkout, without "
        f"printing.\n"
        f"The installer printed:\n{output}")


def failed_message(machine, reference_checkout, step, exit_code, output, why_no_task,
                   owner_instructions=""):
    owner = f"If you are {OWNING_AGENT_SEAT}"
    return (
        f"{PROGRAM}: FAILED — {failed_step_sentence(machine, reference_checkout, step, exit_code)} "
        f"The agent-seat {OWNING_AGENT_SEAT} on ned-box owns the installer and fixes its "
        f"failures, and this failure was not handed to it: {why_no_task}\n"
        + find_and_fix_cause_instruction(owner, machine)
        + kept_line_instruction(machine, f"{owner} and the installer printed a KEPT line", step)
        + owner_instructions
        + rerun_instruction(owner, machine, reference_checkout)
        + user_only_fix_instruction(f"{owner} and ")
        + f"If you are a subagent, give this whole message to the agent that dispatched you.\n"
        f"If you are any other agent, send this whole message to {OWNING_AGENT_SEAT} with "
        f"Claude Code's SendMessage tool, addressed to {OWNING_AGENT_SEAT}; if "
        f"{OWNING_AGENT_SEAT} cannot be reached, tell the user that the scheduled-jobs "
        f"installer's {step} step failed on {machine}, quoting this whole message.\n"
        f"If you are the user, paste this whole message into {OWNING_AGENT_SEAT}'s session.\n"
        f"The installer printed:\n{output}")


def write_failure_owner_instructions(list_directory):
    return (
        f"If you are {OWNING_AGENT_SEAT}, also put right, on ned-box, what stopped the task "
        f"write, such as the permissions of {list_directory} or a file where that directory "
        f"should be.\n")


def open_tasks_with_subject(list_directory, subject):
    """Return (path, task) for each task of the subject not marked completed."""
    found = []
    for path in sorted(list_directory.glob("*.json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if task.get("status") != "completed" and task.get("subject") == subject:
            found.append((path, task))
    return found


def first_failed_installer_step(installer):
    """Return (step, exit code, output) of the first step that exits nonzero, or None."""
    for step in INSTALLER_STEPS:
        ran = subprocess.run([sys.executable, installer, step], capture_output=True, text=True)
        if ran.returncode != 0:
            output = "\n".join(part for part in (ran.stdout.strip(), ran.stderr.strip())
                               if part) or "(nothing)"
            return step, ran.returncode, output
    return None


def main(environment=None, argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog="Git runs this from scripts/git-client-side-hooks/post-merge after every merge, "
               "with no options.")
    parser.add_argument(PRINT_OUTCOME_COMMAND_LINE_FLAG, action="store_true",
                        help="for a run by hand: print one line saying how the run ended, "
                             "where the hook's run prints nothing")
    print_outcome = parser.parse_args(argv).print_outcome

    def outcome(line):
        if print_outcome:
            print(line)
    environment = os.environ if environment is None else environment
    reference_checkouts = dict(REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME)
    if environment.get(NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE):
        reference_checkouts[NED_BOX] = environment[
            NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE]
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        return EXIT_DONE
    checkout = os.path.realpath(top.stdout.strip())
    machine = next((name for name, path in reference_checkouts.items()
                    if os.path.realpath(path) == checkout), None)
    if machine is None:
        outcome(f"{checkout} is not a reference-checkout, so nothing was run; run this in "
                f"{reference_checkouts[NED_BOX]} on ned-box or {reference_checkouts[MAC]} on the "
                f"Mac.")
        return EXIT_DONE
    reference_checkout = reference_checkouts[machine]
    installer = environment.get(SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE) \
        or str(GENERAL_TOOLS / Path(SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY).name)
    failed = first_failed_installer_step(installer)
    if machine != NED_BOX:
        if failed is None:
            outcome(f"Both installer steps, {INSTALL} and then {REMOVE_NOT_IN_TABLE}, exited 0 "
                    f"on {machine}.")
            return EXIT_DONE
        print(failed_message(machine, reference_checkout, *failed,
                             f"{OWNING_AGENT_SEAT}'s task list is on ned-box, and this program "
                             f"writes a task only on ned-box."), file=sys.stderr)
        return EXIT_FAILED
    task_lists_directory = Path(
        environment.get(AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE)
        or Path.home() / ".claude" / "tasks")
    list_directory = task_lists_directory / f"nedsnodes-{OWNING_AGENT_SEAT}-tasks"
    subject = SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST
    if failed is None:
        marked = []
        try:
            if list_directory.is_dir():
                for path, task in open_tasks_with_subject(list_directory, subject):
                    agent_seat_task_file.agent_seat_task_list_task_file_rewrite(
                        path, {**task, "status": "completed"})
                    marked.append(path.name)
        except OSError as error:
            # The hook's run leaves this unreported: the open task's rerun shows the steps work.
            outcome(f"Both installer steps, {INSTALL} and then {REMOVE_NOT_IN_TABLE}, exited 0 "
                    f"on ned-box, but marking the open task completed failed: "
                    f"{type(error).__name__}: {error}. Put right what stopped it and run this "
                    f"again.")
            return EXIT_DONE
        outcome(f"Both installer steps, {INSTALL} and then {REMOVE_NOT_IN_TABLE}, exited 0 on "
                f"ned-box; open tasks marked completed: {', '.join(marked) or 'none'}.")
        return EXIT_DONE
    description = failed_step_task_description(reference_checkout, *failed)
    try:
        list_directory.mkdir(parents=True, exist_ok=True)
        open_tasks = open_tasks_with_subject(list_directory, subject)
        for path, task in open_tasks:
            agent_seat_task_file.agent_seat_task_list_task_file_rewrite(
                path, {**task, "description": description})
        if not open_tasks:
            agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
                list_directory, subject, description)
    except OSError as error:
        print(failed_message(machine, reference_checkout, *failed,
                             f"writing the task into the task list directory {list_directory} "
                             f"failed: {type(error).__name__}: {error}",
                             write_failure_owner_instructions(list_directory)),
              file=sys.stderr)
        return EXIT_FAILED
    outcome(f"The {failed[0]} step failed again on ned-box (exit {failed[1]}); its output is in "
            f"the open task with the subject \"{subject}\" in {list_directory}.")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
