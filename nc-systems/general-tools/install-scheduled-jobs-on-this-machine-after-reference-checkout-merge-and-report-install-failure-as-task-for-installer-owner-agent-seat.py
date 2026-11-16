#!/usr/bin/env python3
"""Run install-scheduled-jobs-on-this-machine.py --install after a merge into a machine's reference-checkout.

Usage (git runs it from scripts/git-client-side-hooks/post-merge, in the
checkout's top directory, after every merge, a fast-forward included):
  nc-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py

Every checkout of the clone runs the same post-merge hook, because
core.hooksPath names the reference-checkout's hook directory. In any checkout
but one of REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME this program does nothing.
In a reference-checkout, it runs the installer beside this file with --install, so a change
merged into the table, scheduled-jobs-on-each-machine.json, or an install that
failed before, is put right at the next pull. The installer's output is not
passed on when it succeeds.

On ned-box, the program keeps a failed install as a task on the task list of
OWNING_AGENT_SEAT, the agent-seat that owns the installer, under the subject
SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST.
An open task is one of that subject not marked completed.

When the installer exits nonzero, each open task gets the latest exit code
and output as its description, or, when none is open, a new task is written
with agent-seat-task-list-new-pending-task-write-common.py; nothing is
printed. Every open task is rewritten, not one of them, so none is left
telling its reader an older failure. When a write fails, the tasks rewritten
before it hold the new description and the rest keep the old one, and the
program prints a FAILED message, as the paragraph after next says.

When the installer exits 0, each open task is marked completed, and nothing
is printed. When marking one completed fails, it and the open tasks after it
stay open, the failure is not reported, and the exit is still 0: an open task
tells its reader to rerun --install, which then shows the install works, and
the next pull that installs successfully marks them completed.

When the task cannot be written, or the installer failed on the Mac, where
OWNING_AGENT_SEAT's task list is not, a FAILED message holding the
installer's output goes to standard error instead: git puts it on its own stderr, and
scripts/checkout-freshness-catch-up.py, which fast-forwards the
reference-checkout, shows the user any FAILED line there.

Git ignores a post-merge hook's exit code; the merge stands either way.

Exit codes: 0 not a reference-checkout, the install succeeded, or its failure
was written as a task; 1 the install failed and writing it as a task failed,
or, on the Mac, was not tried, with the FAILED message on standard error.

Each *_TEST_OVERRIDE_ENVIRONMENT_VARIABLE constant names an environment
variable whose value, when set, replaces a path, for
nc-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat-test.py,
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
    nedschorus-<OWNING_AGENT_SEAT>-tasks in it.
"""

# Messages here follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.

import argparse
import contextlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parent
PROGRAM = "nc-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py"
SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY = (
    "nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py")
OWNING_AGENT_SEAT = "reboot-test"
NED_BOX = "ned-box"
MAC = "the Mac"
EXIT_DONE = 0
EXIT_FAILED = 1

SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE")
NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE")
AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE")


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
    NED_BOX: f"{ned_box_paths.NED_BOX_HOME}/Projects/nedschorus",
    MAC: str(Path(mac_reference_checkout.MAC_REFERENCE_CHECKOUT_LAUNCHER_SCRIPTS_DIRECTORY_PATH).parent),
}
SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST = (
    "Scheduled jobs: nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py "
    "--install failed after a pull into ned-box's reference-checkout")


def install_command_text(reference_checkout):
    return (f"python3 {reference_checkout}/"
            f"{SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY} --install")


def install_failed_task_description(reference_checkout, exit_code, output):
    return (
        f"After the latest merge into ned-box's reference-checkout, {reference_checkout}, its "
        f"post-merge hook ran `{install_command_text(reference_checkout)}`, which exited "
        f"{exit_code}, so ned-box's crontab may not hold the jobs that "
        f"nc-systems/general-tools/scheduled-jobs-on-each-machine.json gives it. The installer "
        f"printed:\n{output}\n"
        f"Find the cause from the installer's FAILED or \"not run\" lines above.\n"
        f"When the cause is in the installer or the table, fix it in a pull request.\n"
        f"When the cause is in ned-box's own state, such as its crontab, put it right on "
        f"ned-box, then run `{install_command_text(reference_checkout)}` on ned-box to confirm "
        f"that it exits 0.\n"
        f"When the fix needs something only the user can do, tell the user what failed, "
        f"quoting the installer's lines, and what he must do.\n"
        f"The post-merge hook runs --install at every pull into the reference-checkout: while "
        f"it fails, it replaces this description with the latest failure, and once it exits 0 "
        f"it marks this task completed. You may mark it completed yourself once the command "
        f"above exits 0.")


def failed_message(machine, reference_checkout, exit_code, output, why_no_task):
    return (
        f"{PROGRAM}: FAILED — after a merge into {machine}'s reference-checkout, "
        f"{reference_checkout}, `{install_command_text(reference_checkout)}` exited {exit_code}, "
        f"so {machine}'s scheduled jobs may not be what "
        f"nc-systems/general-tools/scheduled-jobs-on-each-machine.json says. The agent-seat "
        f"{OWNING_AGENT_SEAT} on ned-box owns the installer and fixes its failures, and this "
        f"failure was not handed to it: {why_no_task}\n"
        f"If you are {OWNING_AGENT_SEAT}, find the cause from the installer's lines below, fix "
        f"it, and have `{install_command_text(reference_checkout)}` run on {machine} to confirm "
        f"that it exits 0.\n"
        f"If you are a subagent, give this whole message to the agent that dispatched you.\n"
        f"If you are any other agent, send this whole message to {OWNING_AGENT_SEAT} with "
        f"Claude Code's SendMessage tool, addressed to {OWNING_AGENT_SEAT}; if "
        f"{OWNING_AGENT_SEAT} cannot be reached, tell the user that the scheduled-jobs install "
        f"failed on {machine}, quoting this whole message.\n"
        f"If you are the user, paste this whole message into {OWNING_AGENT_SEAT}'s session.\n"
        f"The installer printed:\n{output}")


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
    installed = subprocess.run([sys.executable, installer, "--install"],
                               capture_output=True, text=True)
    output = "\n".join(part for part in (installed.stdout.strip(), installed.stderr.strip())
                       if part) or "(nothing)"
    if machine != NED_BOX:
        if installed.returncode == 0:
            return EXIT_DONE
        print(failed_message(machine, reference_checkout, installed.returncode, output,
                             f"{OWNING_AGENT_SEAT}'s task list is on ned-box, and this program "
                             f"writes a task only on ned-box."), file=sys.stderr)
        return EXIT_FAILED
    task_lists_directory = Path(
        environment.get(AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE)
        or Path.home() / ".claude" / "tasks")
    list_directory = task_lists_directory / f"nedschorus-{OWNING_AGENT_SEAT}-tasks"
    subject = SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST
    if installed.returncode == 0:
        if list_directory.is_dir():
            with contextlib.suppress(OSError):
                for path, task in open_tasks_with_subject(list_directory, subject):
                    agent_seat_task_file.agent_seat_task_list_task_file_rewrite(
                        path, {**task, "status": "completed"})
        return EXIT_DONE
    description = install_failed_task_description(reference_checkout, installed.returncode, output)
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
        print(failed_message(machine, reference_checkout, installed.returncode, output,
                             f"writing the task into the task list directory {list_directory} "
                             f"failed: {type(error).__name__}: {error}\n"
                             f"If you are {OWNING_AGENT_SEAT}, put right, on ned-box, what "
                             f"stopped that write, such as the permissions of {list_directory} "
                             f"or a file where that directory should be. Then run `cd "
                             f"{reference_checkout} && python3 {PROGRAM}` on ned-box, which runs "
                             f"the install again.\n"
                             f"If that install fails again, the program writes the failure as a "
                             f"task and exits 0 with nothing printed; if it prints a FAILED "
                             f"message naming the task list directory and exits 1, the write still "
                             f"fails.\n"
                             f"If that install exits 0, the program prints nothing and exits 0, "
                             f"and the failure needs no task."),
              file=sys.stderr)
        return EXIT_FAILED
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main(argv=sys.argv[1:]))
