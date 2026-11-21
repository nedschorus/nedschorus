#!/usr/bin/env python3
"""Run install-scheduled-jobs-on-this-machine.py --install, then --remove-not-in-table, after a merge into a machine's reference-checkout.

Usage (git runs it from scripts/git-client-side-hooks/post-merge, in the
checkout's top directory, after every merge, a fast-forward included):
  nn-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py

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
SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST,
with SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_MARKER_METADATA_KEY set to true in its
metadata. An open task is one carrying that key, whatever its subject, not
marked completed: the subject names paths and options that a rename changes.

When a step fails, each open task gets as its description the failed step's
option, exit code and output, or, when none is open, a new task is written
with agent-seat-task-list-new-pending-task-write-common.py; nothing is
printed. Every open task is rewritten, not one of them, so none is left
telling its reader an older failure. When a write fails, the tasks rewritten
before it hold the new description and the rest keep the old one, and the
program prints a FAILED message, as the paragraph after next says.

When both steps exit 0, each open task is marked completed, and nothing is
printed. When marking one completed fails, it and the open tasks after it
stay open, the failure is not reported, and the exit is still 0: an open task
tells its reader to rerun both steps, which then shows they work, and the
next pull at which both succeed marks them completed.

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
import contextlib
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
SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_MARKER_METADATA_KEY = "is_scheduled_jobs_installer_failure_task"
INSTALL = "--install"
REMOVE_NOT_IN_TABLE = "--remove-not-in-table"
INSTALLER_STEPS = (INSTALL, REMOVE_NOT_IN_TABLE)
SCHEDULED_JOBS_TABLE = "nn-systems/general-tools/scheduled-jobs-on-each-machine.json"
WHAT_A_FAILED_STEP_MAY_LEAVE_ON_THE_MACHINE = {
    INSTALL: f"may not run every job that {SCHEDULED_JOBS_TABLE} gives it",
    REMOVE_NOT_IN_TABLE: f"may still run a job that {SCHEDULED_JOBS_TABLE} does not give it",
}


def step_command_text(reference_checkout, step):
    return (f"python3 {reference_checkout}/"
            f"{SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY} {step}")


def every_step_command_text(reference_checkout):
    return " && ".join(step_command_text(reference_checkout, step) for step in INSTALLER_STEPS)


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


def failed_step_task_description(reference_checkout, step, exit_code, output):
    sentence = failed_step_sentence(NED_BOX, reference_checkout, step, exit_code)
    return (
        f"{sentence[0].upper()}{sentence[1:]} The installer printed:\n{output}\n"
        f"Find the cause from the installer's FAILED, KEPT or \"not run\" lines above.\n"
        f"When the cause is in the installer or the table, fix it in a pull request.\n"
        f"When the cause is in ned-box's own state, such as its crontab, put it right on "
        f"ned-box, then run `{every_step_command_text(reference_checkout)}` on ned-box to "
        f"confirm that both exit 0.\n"
        f"{kept_line_instruction(NED_BOX, 'When the installer printed a KEPT line', step)}"
        f"When the fix needs something only the user can do, tell the user what failed, "
        f"quoting the installer's lines, and what he must do.\n"
        f"The post-merge hook runs both steps at every pull into the reference-checkout: while "
        f"either fails, it replaces this description with the latest failure, and once both "
        f"exit 0 it marks this task completed. You may mark it completed yourself once the "
        f"commands above both exit 0.")


def failed_message(machine, reference_checkout, step, exit_code, output, why_no_task):
    return (
        f"{PROGRAM}: FAILED — {failed_step_sentence(machine, reference_checkout, step, exit_code)} "
        f"The agent-seat {OWNING_AGENT_SEAT} on ned-box owns the installer and fixes its "
        f"failures, and this failure was not handed to it: {why_no_task}\n"
        f"If you are {OWNING_AGENT_SEAT}, find the cause from the installer's lines below, fix "
        f"it, and have `{every_step_command_text(reference_checkout)}` run on {machine} to "
        f"confirm that both exit 0.\n"
        + kept_line_instruction(
            machine, f"If you are {OWNING_AGENT_SEAT} and the installer printed a KEPT line", step)
        + f"If you are a subagent, give this whole message to the agent that dispatched you.\n"
        f"If you are any other agent, send this whole message to {OWNING_AGENT_SEAT} with "
        f"Claude Code's SendMessage tool, addressed to {OWNING_AGENT_SEAT}; if "
        f"{OWNING_AGENT_SEAT} cannot be reached, tell the user that the scheduled-jobs "
        f"installer's {step} step failed on {machine}, quoting this whole message.\n"
        f"If you are the user, paste this whole message into {OWNING_AGENT_SEAT}'s session.\n"
        f"The installer printed:\n{output}")


def scheduled_jobs_installer_failure_tasks_still_pending_or_in_progress(task_list_directory):
    """Return (path, task) for each task carrying the installer-failure metadata key and not
    marked completed."""
    found = []
    for path in sorted(task_list_directory.glob("*.json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        metadata = task.get("metadata")
        if (task.get("status") != "completed" and isinstance(metadata, dict)
                and metadata.get(SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_MARKER_METADATA_KEY) is True):
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
    argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog="Git runs this from scripts/git-client-side-hooks/post-merge after every merge; "
               "it takes no options.").parse_args(argv)
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
        return EXIT_DONE
    reference_checkout = reference_checkouts[machine]
    installer = environment.get(SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE) \
        or str(GENERAL_TOOLS / Path(SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY).name)
    failed = first_failed_installer_step(installer)
    if machine != NED_BOX:
        if failed is None:
            return EXIT_DONE
        print(failed_message(machine, reference_checkout, *failed,
                             f"{OWNING_AGENT_SEAT}'s task list is on ned-box, and this program "
                             f"writes a task only on ned-box."), file=sys.stderr)
        return EXIT_FAILED
    task_lists_directory = Path(
        environment.get(AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE)
        or Path.home() / ".claude" / "tasks")
    list_directory = task_lists_directory / f"nedsnodes-{OWNING_AGENT_SEAT}-tasks"
    if failed is None:
        if list_directory.is_dir():
            with contextlib.suppress(OSError):
                for path, task in scheduled_jobs_installer_failure_tasks_still_pending_or_in_progress(
                        list_directory):
                    agent_seat_task_file.agent_seat_task_list_task_file_rewrite(
                        path, {**task, "status": "completed"})
        return EXIT_DONE
    description = failed_step_task_description(reference_checkout, *failed)
    try:
        list_directory.mkdir(parents=True, exist_ok=True)
        open_tasks = scheduled_jobs_installer_failure_tasks_still_pending_or_in_progress(
            list_directory)
        for path, task in open_tasks:
            agent_seat_task_file.agent_seat_task_list_task_file_rewrite(
                path, {**task, "description": description})
        if not open_tasks:
            agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
                list_directory,
                SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST,
                description, {SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_MARKER_METADATA_KEY: True})
    except OSError as error:
        print(failed_message(machine, reference_checkout, *failed,
                             f"writing the task into the task list directory {list_directory} "
                             f"failed: {type(error).__name__}: {error}\n"
                             f"If you are {OWNING_AGENT_SEAT}, put right, on ned-box, what "
                             f"stopped that write, such as the permissions of {list_directory} "
                             f"or a file where that directory should be. Then run `cd "
                             f"{reference_checkout} && python3 {PROGRAM}` on ned-box, which runs "
                             f"both steps again.\n"
                             f"If a step fails again, the program writes the failure as a "
                             f"task on your task list and exits 0 with nothing printed; if it "
                             f"prints a FAILED message naming the task list directory and exits 1, "
                             f"the write still fails, so find what else stops it.\n"
                             f"If both steps exit 0, the program prints nothing, writes no task "
                             f"and exits 0, and nothing needs a task."),
              file=sys.stderr)
        return EXIT_FAILED
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
